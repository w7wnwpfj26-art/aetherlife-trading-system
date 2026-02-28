"""
增强版 Orchestrator
为 LangGraph 集成做准备，当前使用加权聚合 + 辩论机制
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

from .schemas import TradeIntent, Action, Market, LangGraphState, DecisionContext, Vote
from .agents import BaseAgent, MarketMakerAgent, RiskGuardAgent, OrderFlowAgent, StatArbAgent, NewsSentimentAgent
from .agent_specialized import ChinaAStockAgent, GlobalStockAgent, CryptoNanoAgent
from .agent_cross_market import CrossMarketLeadLagAgent, ForexMicroAgent, FuturesMicroAgent, SentimentAgent
from .debate import BullAgent, BearAgent, JudgeAgent
from ..perception.models import MarketSnapshot
from ..memory.store import MemoryStore

logger = logging.getLogger(__name__)


class EnhancedOrchestrator:
    """
    增强版多 Agent 协调器
    
    功能：
    1. 支持多市场专业化 Agent
    2. 聚合决策 + 可选辩论
    3. 为 LangGraph 状态机预留接口
    4. 支持并行 Agent 执行
    """
    
    def __init__(
        self,
        agents: Optional[List[BaseAgent]] = None,
        debate_enabled: bool = False,
        weights: Optional[Dict[str, float]] = None,
        enable_specialized_agents: bool = True,
    ):
        # 基础 Agent
        self.base_agents = agents or [
            MarketMakerAgent(),
            OrderFlowAgent(),
            StatArbAgent(),
            NewsSentimentAgent(),
        ]
        
        # 专业化 Agent（多市场）
        self.specialized_agents = []
        if enable_specialized_agents:
            self.specialized_agents = [
                ChinaAStockAgent(),
                GlobalStockAgent(),
                CryptoNanoAgent(),
                CrossMarketLeadLagAgent(),
                ForexMicroAgent(),
                FuturesMicroAgent(),
                SentimentAgent(),
            ]
        
        # 合并所有 Agent
        self.all_agents = self.base_agents + self.specialized_agents
        
        # 风控 Agent
        self.risk_guard = RiskGuardAgent()
        
        # 辩论机制
        self.debate_enabled = debate_enabled
        self._bull = BullAgent()
        self._bear = BearAgent()
        self._judge = JudgeAgent()
        
        # Agent 权重
        self.weights = weights or {a.agent_id: 1.0 for a in self.all_agents}
        
        # 市场类型权重（根据当前市场动态调整）
        self.market_weights: Dict[Market, float] = {
            Market.CRYPTO: 1.0,
            Market.A_STOCK: 0.8,
            Market.US_STOCK: 0.9,
            Market.FOREX: 0.7,
            Market.FUTURES: 0.8,
        }
    
    async def run(
        self,
        snapshot: MarketSnapshot,
        memory: MemoryStore,
        market: Optional[Market] = None,
    ) -> TradeIntent:
        """
        执行一轮决策
        
        Args:
            snapshot: 市场快照
            memory: 记忆存储
            market: 指定市场类型（可选，自动推断）
        
        Returns:
            最终交易意图
        """
        # 1. 推断市场类型
        if market is None:
            market = self._infer_market(snapshot)
        
        # 2. 构建上下文
        context = memory.get_context_for_llm(max_items=30)
        
        # 3. 选择相关 Agent
        relevant_agents = self._select_relevant_agents(market)
        
        logger.info(f"运行 {len(relevant_agents)} 个相关 Agent: {[a.agent_id for a in relevant_agents]}")
        
        # 4. 并行执行 Agent
        if self.debate_enabled:
            combined = await self._run_debate(snapshot, context)
        else:
            intents = await asyncio.gather(
                *[a.run(snapshot, context) for a in relevant_agents],
                return_exceptions=True
            )
            
            # 过滤异常
            valid_intents = [i for i in intents if isinstance(i, TradeIntent)]
            
            if not valid_intents:
                return TradeIntent(
                    action=Action.HOLD,
                    market=market,
                    symbol=snapshot.symbol,
                    reason="所有 Agent 执行失败",
                    confidence=0.0
                )
            
            combined = self._aggregate(valid_intents, relevant_agents)
        
        # 5. 风控否决检查
        daily_pnl = memory.get_daily_pnl()
        if self.risk_guard.should_veto(combined, daily_pnl):
            combined = TradeIntent(
                action=Action.HOLD,
                market=market,
                symbol=snapshot.symbol,
                reason="风控否决",
                confidence=0.0,
                agent_id="risk_guard"
            )
        
        # 6. 应用市场权重
        combined.confidence *= self.market_weights.get(market, 1.0)
        
        return combined
    
    def _infer_market(self, snapshot: MarketSnapshot) -> Market:
        """
        根据交易所和品种推断市场类型
        
        Args:
            snapshot: 市场快照
        
        Returns:
            Market 枚举
        """
        exchange = snapshot.exchange.lower()
        symbol = snapshot.symbol.upper()
        
        # 加密货币
        if exchange in ["binance", "bybit", "okx", "coinbase"]:
            return Market.CRYPTO
        
        # A股（SEHK via Stock Connect）
        if exchange == "sehk" or symbol.startswith("6") or symbol.startswith("0") or symbol.startswith("3"):
            return Market.A_STOCK
        
        # 美股
        if exchange in ["nasdaq", "nyse", "smart"]:
            return Market.US_STOCK
        
        # 外汇
        if "forex" in exchange or "/" in symbol and len(symbol) == 7:  # EUR/USD
            return Market.FOREX
        
        # 期货
        if "future" in exchange or "cme" in exchange:
            return Market.FUTURES
        
        # 默认加密货币
        return Market.CRYPTO
    
    def _select_relevant_agents(self, market: Market) -> List[BaseAgent]:
        """
        根据市场类型选择相关 Agent
        
        Args:
            market: 市场类型
        
        Returns:
            相关 Agent 列表
        """
        relevant = []
        
        # 始终包含的通用 Agent
        for agent in self.base_agents:
            relevant.append(agent)
        
        # 根据市场类型添加专业化 Agent
        agent_map = {
            Market.CRYPTO: ["crypto_nano", "sentiment", "cross_market"],
            Market.A_STOCK: ["china_astock", "sentiment", "cross_market"],
            Market.US_STOCK: ["global_stock", "sentiment", "cross_market"],
            Market.HK_STOCK: ["global_stock", "sentiment"],
            Market.FOREX: ["forex_micro"],
            Market.FUTURES: ["futures_micro", "cross_market"],
        }
        
        relevant_ids = agent_map.get(market, [])
        
        for agent in self.specialized_agents:
            if agent.agent_id in relevant_ids:
                relevant.append(agent)
        
        return relevant
    
    async def _run_debate(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """Bull / Bear 并行 → Judge 裁决"""
        bull_intent, bear_intent = await asyncio.gather(
            self._bull.run(snapshot, context),
            self._bear.run(snapshot, context),
        )
        
        bull_vote = self._bull.vote(bull_intent)
        bear_vote = self._bear.vote(bear_intent)
        
        return self._judge.decide(bull_vote, bear_vote)
    
    def _aggregate(self, intents: List[TradeIntent], agents: List[BaseAgent]) -> TradeIntent:
        """
        聚合多个 Agent 的决策
        
        算法：
        1. 按 action 分组
        2. 加权平均 quantity_pct 和 confidence
        3. 选择得分最高的 action
        """
        if not intents:
            return TradeIntent(
                action=Action.HOLD,
                reason="无有效决策",
                confidence=0.0
            )
        
        # 按 action 分组统计
        action_scores: Dict[Action, float] = {
            Action.HOLD: 0.0,
            Action.BUY: 0.0,
            Action.SELL: 0.0,
        }
        
        action_details: Dict[Action, List[tuple]] = {
            Action.HOLD: [],
            Action.BUY: [],
            Action.SELL: [],
        }
        
        for idx, intent in enumerate(intents):
            agent = agents[idx] if idx < len(agents) else None
            weight = self.weights.get(agent.agent_id, 1.0) if agent else 1.0
            
            # 计算得分：quantity_pct * confidence * weight
            score = (intent.quantity_pct or 0) * (intent.confidence or 0) * weight
            
            action_scores[intent.action] += score
            action_details[intent.action].append((intent, weight))
        
        # 找到得分最高的 action
        best_action = max(action_scores.items(), key=lambda x: x[1])[0]
        
        if best_action == Action.HOLD or action_scores[best_action] <= 0:
            return TradeIntent(
                action=Action.HOLD,
                market=intents[0].market if intents else Market.CRYPTO,
                symbol=intents[0].symbol if intents else "",
                reason="综合决策：观望",
                confidence=0.5
            )
        
        # 计算该 action 的平均 quantity_pct 和 confidence
        details = action_details[best_action]
        total_weight = sum(w for _, w in details)
        
        if total_weight <= 0:
            total_weight = 1.0
        
        avg_quantity = sum(i.quantity_pct * w for i, w in details) / total_weight
        avg_confidence = sum(i.confidence * w for i, w in details) / total_weight
        
        # 收集理由
        reasons = [i.reason for i, _ in details if i.reason]
        combined_reason = f"多Agent决策({best_action}): " + "; ".join(reasons[:3])
        
        return TradeIntent(
            action=best_action,
            market=intents[0].market,
            symbol=intents[0].symbol,
            quantity_pct=min(0.20, avg_quantity),  # 限制最大仓位
            reason=combined_reason,
            confidence=min(0.85, avg_confidence),
            agent_id="orchestrator",
            metadata={
                "agent_count": len(details),
                "action_scores": {k.value: v for k, v in action_scores.items()}
            }
        )
    
    def update_market_weights(self, market: Market, weight: float):
        """动态调整市场权重"""
        self.market_weights[market] = max(0.0, min(1.0, weight))
        logger.info(f"更新市场权重: {market} = {weight:.2f}")
    
    def update_agent_weights(self, agent_id: str, weight: float):
        """动态调整 Agent 权重"""
        self.weights[agent_id] = max(0.0, min(2.0, weight))
        logger.info(f"更新Agent权重: {agent_id} = {weight:.2f}")
