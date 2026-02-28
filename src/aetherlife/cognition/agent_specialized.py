"""
中国A股专家 Agent
专门处理A股交易的特殊逻辑
"""

import logging
from typing import Optional
from datetime import datetime, time as dt_time

from .agents import BaseAgent
from .schemas import TradeIntent, Action, Market, DecisionContext
from ..perception.models import MarketSnapshot

logger = logging.getLogger(__name__)


class ChinaAStockAgent(BaseAgent):
    """
    中国A股专家 Agent
    
    特殊处理：
    1. 北向额度监控（Stock Connect）
    2. 交易时段限制（09:30-11:30, 13:00-15:00）
    3. 涨跌停检测
    4. 印花税成本计算
    5. T+1 交易规则
    """
    
    def __init__(self):
        super().__init__("china_astock")
        self.trading_hours = [
            (dt_time(9, 30), dt_time(11, 30)),  # 上午
            (dt_time(13, 0), dt_time(15, 0))   # 下午
        ]
        
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """
        分析A股市场并输出交易意图
        
        Args:
            snapshot: 市场快照
            context: 记忆上下文
        
        Returns:
            TradeIntent
        """
        # 1. 检查交易时段
        if not self._is_trading_hours():
            return TradeIntent(
                action=Action.HOLD,
                market=Market.A_STOCK,
                symbol=snapshot.symbol,
                reason="A股休市时段",
                confidence=0.0
            )
        
        # 2. 检查涨跌停
        if self._is_limit_up_or_down(snapshot):
            return TradeIntent(
                action=Action.HOLD,
                market=Market.A_STOCK,
                symbol=snapshot.symbol,
                reason="接近涨跌停，避免追涨杀跌",
                confidence=0.0
            )
        
        # 3. 检查北向额度
        northbound_quota_pct = self._get_northbound_quota_pct(context)
        if northbound_quota_pct is not None and northbound_quota_pct < 10:
            # 额度不足10%，谨慎操作
            logger.warning(f"北向额度不足: {northbound_quota_pct:.1f}%")
        
        # 4. 基础技术分析
        intent = self._analyze_technicals(snapshot)
        
        # 5. 考虑印花税成本（卖出时0.1%）
        if intent.action == Action.SELL:
            # 降低卖出信号的 confidence，因为有额外成本
            intent.confidence *= 0.95
            intent.reason += " | 已考虑印花税成本"
        
        intent.market = Market.A_STOCK
        return intent
    
    def _is_trading_hours(self) -> bool:
        """检查是否在交易时段"""
        now = datetime.now().time()
        
        for start, end in self.trading_hours:
            if start <= now <= end:
                return True
        
        return False
    
    def _is_limit_up_or_down(self, snapshot: MarketSnapshot) -> bool:
        """
        检查是否接近涨跌停
        
        A股涨跌停限制：
        - 主板/创业板：±10%
        - 科创板/创业板注册制：±20%
        - ST股票：±5%
        """
        if not snapshot.ticker_24h:
            return False
        
        last_price = snapshot.last_price
        prev_close = snapshot.ticker_24h.get('close', 0)
        
        if prev_close <= 0:
            return False
        
        change_pct = (last_price - prev_close) / prev_close
        
        # 简化判断：接近±9.5%视为涨跌停附近
        if abs(change_pct) >= 0.095:
            return True
        
        return False
    
    def _get_northbound_quota_pct(self, context: str) -> Optional[float]:
        """
        从上下文中提取北向额度百分比
        
        Returns:
            剩余额度百分比 (0-100)
        """
        # 简化实现：从 context 字符串中解析
        # 实际应该从 DecisionContext 对象获取
        if "northbound_quota" in context.lower():
            try:
                # 示例：context 包含 "northbound_quota: 45.2%"
                parts = context.split("northbound_quota:")
                if len(parts) > 1:
                    pct_str = parts[1].split("%")[0].strip()
                    return float(pct_str)
            except Exception:
                pass
        
        return None
    
    def _analyze_technicals(self, snapshot: MarketSnapshot) -> TradeIntent:
        """
        技术分析（简化版）
        
        实际应该使用更复杂的策略：
        - MA 均线
        - MACD
        - 成交量分析
        - 资金流向
        """
        ob = snapshot.orderbook
        
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(
                action=Action.HOLD,
                symbol=snapshot.symbol,
                reason="订单簿数据不足",
                confidence=0.0
            )
        
        # 1. 买卖压力分析
        bid_vol = sum(q for _, q in ob.bids[:5])
        ask_vol = sum(q for _, q in ob.asks[:5])
        
        # 2. 价差分析
        spread_bps = ob.spread_bps()
        
        # 简单规则
        if spread_bps > 50:
            # 价差过大，观望
            return TradeIntent(
                action=Action.HOLD,
                symbol=snapshot.symbol,
                quantity_pct=0.0,
                reason=f"A股价差过大 {spread_bps:.1f} bps",
                confidence=0.6
            )
        
        if bid_vol > ask_vol * 1.3:
            # 买盘强劲
            return TradeIntent(
                action=Action.BUY,
                symbol=snapshot.symbol,
                quantity_pct=0.08,  # 保守仓位
                reason=f"A股买盘压力 (买/卖={bid_vol/ask_vol:.2f})",
                confidence=0.55
            )
        
        if ask_vol > bid_vol * 1.3:
            # 卖盘压力
            return TradeIntent(
                action=Action.SELL,
                symbol=snapshot.symbol,
                quantity_pct=0.08,
                reason=f"A股卖盘压力 (卖/买={ask_vol/bid_vol:.2f})",
                confidence=0.55
            )
        
        return TradeIntent(
            action=Action.HOLD,
            symbol=snapshot.symbol,
            reason="A股订单流中性",
            confidence=0.5
        )


class GlobalStockAgent(BaseAgent):
    """
    全球股票专家 Agent（美股、港股、国际股票）
    
    特点：
    1. 盘前盘后交易
    2. Fractional shares 支持
    3. 多市场时区处理
    """
    
    def __init__(self):
        super().__init__("global_stock")
    
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """全球股票分析"""
        ob = snapshot.orderbook
        
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.US_STOCK,
                symbol=snapshot.symbol,
                reason="订单簿数据不足",
                confidence=0.0
            )
        
        # 简化的动量策略
        spread_bps = ob.spread_bps()
        mid_price = ob.mid_price()
        
        # 根据 spread 判断流动性
        if spread_bps > 30:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.US_STOCK,
                symbol=snapshot.symbol,
                reason=f"流动性不足，Spread {spread_bps:.1f} bps",
                confidence=0.5
            )
        
        # 买卖压力
        bid_vol = sum(q for _, q in ob.bids[:10])
        ask_vol = sum(q for _, q in ob.asks[:10])
        
        if bid_vol > ask_vol * 1.4:
            return TradeIntent(
                action=Action.BUY,
                market=Market.US_STOCK,
                symbol=snapshot.symbol,
                quantity_pct=0.10,
                reason=f"全球股票买盘强 (比例={bid_vol/ask_vol:.2f})",
                confidence=0.60
            )
        
        if ask_vol > bid_vol * 1.4:
            return TradeIntent(
                action=Action.SELL,
                market=Market.US_STOCK,
                symbol=snapshot.symbol,
                quantity_pct=0.10,
                reason=f"全球股票卖盘强 (比例={ask_vol/bid_vol:.2f})",
                confidence=0.60
            )
        
        return TradeIntent(
            action=Action.HOLD,
            market=Market.US_STOCK,
            symbol=snapshot.symbol,
            reason="全球股票订单流平衡",
            confidence=0.5
        )


class CryptoNanoAgent(BaseAgent):
    """
    加密货币 nano 永续专家 Agent
    
    特点：
    1. 24/7 交易
    2. 高杠杆（nano 通常是 mini 合约）
    3. 资金费率监控
    4. 高频策略适用
    """
    
    def __init__(self):
        super().__init__("crypto_nano")
    
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """加密货币分析"""
        ob = snapshot.orderbook
        
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                reason="订单簿数据不足",
                confidence=0.0
            )
        
        # 加密货币更激进的策略
        spread_bps = ob.spread_bps()
        
        if spread_bps > 20:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                reason=f"加密货币价差过大 {spread_bps:.1f} bps",
                confidence=0.5
            )
        
        # 订单流分析
        bid_vol = sum(q for _, q in ob.bids[:20])
        ask_vol = sum(q for _, q in ob.asks[:20])
        
        # 加密货币阈值更低（更敏感）
        if bid_vol > ask_vol * 1.2:
            return TradeIntent(
                action=Action.BUY,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.12,  # 相对激进
                reason=f"加密货币买盘压力 (比例={bid_vol/ask_vol:.2f})",
                confidence=0.62
            )
        
        if ask_vol > bid_vol * 1.2:
            return TradeIntent(
                action=Action.SELL,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.12,
                reason=f"加密货币卖盘压力 (比例={ask_vol/bid_vol:.2f})",
                confidence=0.62
            )
        
        return TradeIntent(
            action=Action.HOLD,
            market=Market.CRYPTO,
            symbol=snapshot.symbol,
            reason="加密货币订单流中性",
            confidence=0.5
        )
