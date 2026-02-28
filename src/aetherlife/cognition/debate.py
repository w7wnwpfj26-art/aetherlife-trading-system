"""
辩论工作流：Bull（多方） / Bear（空方） / Judge（裁决）
Phase 1：可替换为 LLM 生成 reasoning
"""

import asyncio
from typing import List

from .schemas import TradeIntent, Action, Vote
from .agents import BaseAgent, MarketMakerAgent, OrderFlowAgent
from ..perception.models import MarketSnapshot
from ..memory.store import MemoryStore


class BullAgent(BaseAgent):
    """多方：偏向做多，从做多角度解读同一快照"""

    def __init__(self):
        super().__init__("bull")
        self._market_maker = MarketMakerAgent()
        self._order_flow = OrderFlowAgent()

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        base = await self._market_maker.run(snapshot, context)
        of = await self._order_flow.run(snapshot, context)
        # 偏向解读为做多
        if base.action == Action.SELL:
            base = TradeIntent(action=Action.HOLD, reason="多方认为卖压可观望", confidence=base.confidence * 0.6)
        if of.action == Action.BUY:
            base = TradeIntent(
                action=Action.BUY,
                quantity_pct=min(0.15, (base.quantity_pct or 0) + 0.05),
                reason="多方: 订单流支持做多",
                confidence=min(0.85, (base.confidence or 0) + 0.1),
            )
        return base

    def vote(self, intent: TradeIntent) -> Vote:
        return Vote(role="bull", action=intent.action, reasoning=intent.reason, confidence=intent.confidence)


class BearAgent(BaseAgent):
    """空方：偏向做空，从做空角度解读"""

    def __init__(self):
        super().__init__("bear")
        self._market_maker = MarketMakerAgent()
        self._order_flow = OrderFlowAgent()

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        base = await self._market_maker.run(snapshot, context)
        of = await self._order_flow.run(snapshot, context)
        if base.action == Action.BUY:
            base = TradeIntent(action=Action.HOLD, reason="空方认为买压不足", confidence=base.confidence * 0.6)
        if of.action == Action.SELL:
            base = TradeIntent(
                action=Action.SELL,
                quantity_pct=min(0.15, (base.quantity_pct or 0) + 0.05),
                reason="空方: 订单流支持做空",
                confidence=min(0.85, (base.confidence or 0) + 0.1),
            )
        return base

    def vote(self, intent: TradeIntent) -> Vote:
        return Vote(role="bear", action=intent.action, reasoning=intent.reason, confidence=intent.confidence)


class JudgeAgent(BaseAgent):
    """裁决方：根据 Bull/Bear 的 Vote 做出最终 TradeIntent"""

    def __init__(self):
        super().__init__("judge")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        return TradeIntent(action=Action.HOLD, reason="Judge 需接收 Bull/Bear 投票后裁决", confidence=0.5)

    def decide(self, bull_vote: Vote, bear_vote: Vote) -> TradeIntent:
        """根据两方投票裁决"""
        b_conf = bull_vote.confidence or 0
        r_conf = bear_vote.confidence or 0
        if b_conf > r_conf + 0.15 and bull_vote.action == Action.BUY:
            return TradeIntent(
                action=Action.BUY,
                quantity_pct=0.1,
                reason=f"裁决: 采纳多方 | {bull_vote.reasoning[:80]}",
                confidence=b_conf,
            )
        if r_conf > b_conf + 0.15 and bear_vote.action == Action.SELL:
            return TradeIntent(
                action=Action.SELL,
                quantity_pct=0.1,
                reason=f"裁决: 采纳空方 | {bear_vote.reasoning[:80]}",
                confidence=r_conf,
            )
        return TradeIntent(
            action=Action.HOLD,
            reason=f"裁决: 分歧 (Bull={b_conf:.2f}, Bear={r_conf:.2f})，观望",
            confidence=0.5,
        )
