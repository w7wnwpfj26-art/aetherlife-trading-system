"""
Worker Agents：专业角色，输出结构化决策
Phase 0：规则 + 简单启发式；Phase 1+：接 LangGraph/CrewAI/LLM
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from .schemas import TradeIntent, Action
from ..perception.models import MarketSnapshot


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """根据市场快照与短期记忆输出交易意图"""
        pass


class MarketMakerAgent(BaseAgent):
    """做市/价差 Agent：看订单簿 spread 与库存"""

    def __init__(self):
        super().__init__("market_maker")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        ob = snapshot.orderbook
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(action=Action.HOLD, reason="无订单簿", confidence=0)
        mid = ob.mid_price()
        spread_bps = ob.spread_bps()
        # 简单规则：spread 过宽偏观望
        if spread_bps > 30:
            return TradeIntent(action=Action.HOLD, reason=f"价差过大 {spread_bps:.1f} bps", confidence=0.6)
        # 买卖压力
        bid_vol = sum(q for _, q in ob.bids[:5])
        ask_vol = sum(q for _, q in ob.asks[:5])
        if bid_vol > ask_vol * 1.2:
            return TradeIntent(action=Action.BUY, quantity_pct=0.1, reason="买盘压力", confidence=0.5)
        if ask_vol > bid_vol * 1.2:
            return TradeIntent(action=Action.SELL, quantity_pct=0.1, reason="卖盘压力", confidence=0.5)
        return TradeIntent(action=Action.HOLD, reason="价差与深度中性", confidence=0.5)


class RiskGuardAgent(BaseAgent):
    """风控 Agent：一票否决，不发起交易只否决"""

    def __init__(self):
        super().__init__("risk_guard")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        # 永远只输出 HOLD 或维持原意；外部逻辑用「是否否决」解释
        return TradeIntent(action=Action.HOLD, reason="风控仅做否决判断", confidence=1.0)

    def should_veto(self, intent: TradeIntent, daily_pnl: float, max_daily_loss_pct: float = 0.05) -> bool:
        """是否否决该笔意图"""
        if intent.action == Action.HOLD:
            return False
        if daily_pnl < -max_daily_loss_pct * 100:  # 假设 pnl 为百分比
            return True
        if intent.confidence < 0.3:
            return True
        return False


class OrderFlowAgent(BaseAgent):
    """订单流/微观结构 Agent"""

    def __init__(self):
        super().__init__("order_flow")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        if not snapshot.orderbook:
            return TradeIntent(action=Action.HOLD, reason="无订单簿", confidence=0)
        ob = snapshot.orderbook
        bid_vol = sum(q for _, q in ob.bids[:10])
        ask_vol = sum(q for _, q in ob.asks[:10])
        if bid_vol > ask_vol * 1.5:
            return TradeIntent(action=Action.BUY, quantity_pct=0.08, reason="订单流偏多", confidence=0.55)
        if ask_vol > bid_vol * 1.5:
            return TradeIntent(action=Action.SELL, quantity_pct=0.08, reason="订单流偏空", confidence=0.55)
        return TradeIntent(action=Action.HOLD, reason="订单流中性", confidence=0.5)


class StatArbAgent(BaseAgent):
    """统计套利 Agent（Phase 1+ 可接协整等）"""

    def __init__(self):
        super().__init__("stat_arb")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        # 单品种 MVP 无价差对，先观望
        return TradeIntent(action=Action.HOLD, reason="单品种无价差对", confidence=0.5)


class NewsSentimentAgent(BaseAgent):
    """新闻/情绪 Agent（Phase 1+ 接 X/新闻 API）"""

    def __init__(self):
        super().__init__("news_sentiment")

    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        return TradeIntent(action=Action.HOLD, reason="情绪模块未接入", confidence=0.5)
