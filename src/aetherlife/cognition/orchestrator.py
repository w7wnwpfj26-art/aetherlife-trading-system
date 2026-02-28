"""
Orchestrator：状态机调度各 Agent，可选 Debate（Bull/Bear/Judge）
Phase 0：顺序调用 + 加权/投票；Phase 1：LangGraph 状态机
"""

import asyncio
from typing import List, Optional

from .schemas import TradeIntent, Action, Vote
from .agents import BaseAgent, MarketMakerAgent, RiskGuardAgent, OrderFlowAgent, StatArbAgent, NewsSentimentAgent
from .debate import BullAgent, BearAgent, JudgeAgent
from ..perception.models import MarketSnapshot
from ..memory.store import MemoryStore


class Orchestrator:
    """多 Agent 协调器：聚合决策 + 可选辩论（Bull/Bear/Judge）"""

    def __init__(
        self,
        agents: Optional[List[BaseAgent]] = None,
        debate_enabled: bool = False,
        weights: Optional[dict] = None,
    ):
        self.agents = agents or [
            MarketMakerAgent(),
            OrderFlowAgent(),
            StatArbAgent(),
            NewsSentimentAgent(),
        ]
        self.risk_guard = RiskGuardAgent()
        self.debate_enabled = debate_enabled
        self.weights = weights or {a.agent_id: 1.0 for a in self.agents}
        self._bull = BullAgent()
        self._bear = BearAgent()
        self._judge = JudgeAgent()

    async def run(
        self,
        snapshot: MarketSnapshot,
        memory: MemoryStore,
    ) -> TradeIntent:
        """执行一轮：可选辩论路径 或 多 Agent 并行聚合 → RiskGuard 否决"""
        context = memory.get_context_for_llm(max_items=20)
        if self.debate_enabled:
            combined = await self._run_debate(snapshot, context)
        else:
            intents = await asyncio.gather(*[a.run(snapshot, context) for a in self.agents])
            combined = self._aggregate(intents)
        daily_pnl = memory.get_daily_pnl()
        if self.risk_guard.should_veto(combined, daily_pnl):
            combined = TradeIntent(action=Action.HOLD, reason="风控否决", confidence=0)
        return combined

    async def _run_debate(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """Bull / Bear 并行 → Judge 裁决"""
        bull_intent, bear_intent = await asyncio.gather(
            self._bull.run(snapshot, context),
            self._bear.run(snapshot, context),
        )
        bull_vote = self._bull.vote(bull_intent)
        bear_vote = self._bear.vote(bear_intent)
        return self._judge.decide(bull_vote, bear_vote)

    def _aggregate(self, intents: List[TradeIntent]) -> TradeIntent:
        """简单加权：按 action 加权平均 quantity_pct 与 confidence"""
        buy_score = 0.0
        sell_score = 0.0
        for idx, i in enumerate(intents):
            w = self.weights.get(self.agents[idx].agent_id, 1.0) if idx < len(self.agents) else 1.0
            score = (i.quantity_pct or 0) * (i.confidence or 0) * w
            if i.action == Action.BUY:
                buy_score += score
            elif i.action == Action.SELL:
                sell_score += score
        # 归一化到 0~1
        total = buy_score + sell_score
        if total <= 0:
            return TradeIntent(action=Action.HOLD, reason="综合观望", confidence=0.5)
        if buy_score > sell_score:
            return TradeIntent(
                action=Action.BUY,
                quantity_pct=min(0.2, buy_score / (len(intents) or 1)),
                reason="多 Agent 偏多",
                confidence=min(0.8, 0.3 + buy_score / (len(intents) or 1) * 0.5),
            )
        return TradeIntent(
            action=Action.SELL,
            quantity_pct=min(0.2, sell_score / (len(intents) or 1)),
            reason="多 Agent 偏空",
            confidence=min(0.8, 0.3 + sell_score / (len(intents) or 1) * 0.5),
        )
