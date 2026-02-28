"""
跨市场套利与情绪分析 Agent
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from .agents import BaseAgent
from .schemas import TradeIntent, Action, Market, CrossMarketSignal
from ..perception.models import MarketSnapshot

logger = logging.getLogger(__name__)


class CrossMarketLeadLagAgent(BaseAgent):
    """
    跨市场 Lead-Lag 套利专家
    
    捕捉市场间的领先-滞后效应：
    1. BTC 先动 → A股/港股科技股跟随
    2. 美股科技股 → A股科技股
    3. 商品期货 → 相关股票
    """
    
    def __init__(self):
        super().__init__("cross_market")
        # 历史价格缓存（用于计算相关性）
        self._price_history: Dict[str, List[tuple]] = {}  # symbol -> [(timestamp, price), ...]
        self._max_history = 100
        
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """跨市场分析"""
        # 更新价格历史
        self._update_price_history(snapshot)
        
        # 检测 Lead-Lag 信号
        signals = self._detect_lead_lag_signals(snapshot)
        
        if not signals:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.CRYPTO,  # 默认
                symbol=snapshot.symbol,
                reason="未检测到跨市场信号",
                confidence=0.5
            )
        
        # 选择最强信号
        best_signal = max(signals, key=lambda s: s.strength)
        
        return TradeIntent(
            action=best_signal.suggested_action,
            market=best_signal.target_market,
            symbol=best_signal.target_symbol,
            quantity_pct=0.08 * best_signal.strength,  # 根据信号强度调整仓位
            reason=f"跨市场信号: {best_signal.reason}",
            confidence=0.5 + 0.3 * best_signal.strength,
            metadata={
                "signal_type": best_signal.signal_type,
                "source_market": best_signal.source_market,
                "lag_seconds": best_signal.lag_seconds,
                "correlation": best_signal.correlation
            }
        )
    
    def _update_price_history(self, snapshot: MarketSnapshot):
        """更新价格历史"""
        symbol = snapshot.symbol
        price = snapshot.last_price
        timestamp = datetime.now()
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        
        self._price_history[symbol].append((timestamp, price))
        
        # 保留最近 N 个数据点
        if len(self._price_history[symbol]) > self._max_history:
            self._price_history[symbol].pop(0)
    
    def _detect_lead_lag_signals(self, snapshot: MarketSnapshot) -> List[CrossMarketSignal]:
        """
        检测 Lead-Lag 信号
        
        简化实现：
        1. BTC 涨 > 2% in 5min → A股科技股可能跟涨
        2. 使用历史数据计算相关性
        """
        signals = []
        
        # 示例：BTC → A股科技股
        if snapshot.symbol in ["BTC/USDT", "BTCUSDT"]:
            btc_change = self._calculate_price_change(snapshot.symbol, minutes=5)
            
            if btc_change is not None and abs(btc_change) > 0.02:
                # BTC 有明显波动
                signals.append(CrossMarketSignal(
                    source_market=Market.CRYPTO,
                    source_symbol=snapshot.symbol,
                    target_market=Market.A_STOCK,
                    target_symbol="300750",  # 示例：宁德时代
                    signal_type="lead_lag",
                    strength=min(abs(btc_change) / 0.05, 1.0),  # 归一化到0-1
                    lag_seconds=300,  # 预期5分钟滞后
                    suggested_action=Action.BUY if btc_change > 0 else Action.SELL,
                    reason=f"BTC 变动 {btc_change*100:.2f}%，预期A股科技股跟随"
                ))
        
        return signals
    
    def _calculate_price_change(self, symbol: str, minutes: int = 5) -> Optional[float]:
        """
        计算过去 N 分钟的价格变化
        
        Returns:
            价格变化百分比（如 0.02 表示涨2%）
        """
        if symbol not in self._price_history:
            return None
        
        history = self._price_history[symbol]
        if len(history) < 2:
            return None
        
        now = datetime.now()
        cutoff = now - timedelta(minutes=minutes)
        
        # 找到 cutoff 时间点附近的价格
        old_price = None
        for ts, price in history:
            if ts >= cutoff:
                old_price = price
                break
        
        if old_price is None:
            old_price = history[0][1]
        
        current_price = history[-1][1]
        
        if old_price <= 0:
            return None
        
        return (current_price - old_price) / old_price


class ForexMicroAgent(BaseAgent):
    """
    外汇 Micro 专家 Agent
    
    特点：
    1. 货币对相关性
    2. 点差敏感
    3. 日内波动捕捉
    """
    
    def __init__(self):
        super().__init__("forex_micro")
    
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """外汇分析"""
        ob = snapshot.orderbook
        
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.FOREX,
                symbol=snapshot.symbol,
                reason="订单簿数据不足",
                confidence=0.0
            )
        
        # 外汇对点差非常敏感
        spread_bps = ob.spread_bps()
        
        if spread_bps > 10:  # 外汇点差通常很小
            return TradeIntent(
                action=Action.HOLD,
                market=Market.FOREX,
                symbol=snapshot.symbol,
                reason=f"外汇点差过大 {spread_bps:.1f} bps",
                confidence=0.5
            )
        
        # 简化的订单流策略
        bid_vol = sum(q for _, q in ob.bids[:10])
        ask_vol = sum(q for _, q in ob.asks[:10])
        
        if bid_vol > ask_vol * 1.25:
            return TradeIntent(
                action=Action.BUY,
                market=Market.FOREX,
                symbol=snapshot.symbol,
                quantity_pct=0.08,
                reason=f"外汇买盘压力 (比例={bid_vol/ask_vol:.2f})",
                confidence=0.58
            )
        
        if ask_vol > bid_vol * 1.25:
            return TradeIntent(
                action=Action.SELL,
                market=Market.FOREX,
                symbol=snapshot.symbol,
                quantity_pct=0.08,
                reason=f"外汇卖盘压力 (比例={ask_vol/bid_vol:.2f})",
                confidence=0.58
            )
        
        return TradeIntent(
            action=Action.HOLD,
            market=Market.FOREX,
            symbol=snapshot.symbol,
            reason="外汇订单流平衡",
            confidence=0.5
        )


class FuturesMicroAgent(BaseAgent):
    """
    期货 Micro 专家 Agent（Micro E-mini ES/NQ、nano BTC/ETH）
    
    特点：
    1. 展期换月处理
    2. 基差分析
    3. 持仓成本
    """
    
    def __init__(self):
        super().__init__("futures_micro")
    
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """期货分析"""
        ob = snapshot.orderbook
        
        if not ob or not ob.bids or not ob.asks:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.FUTURES,
                symbol=snapshot.symbol,
                reason="订单簿数据不足",
                confidence=0.0
            )
        
        spread_bps = ob.spread_bps()
        
        if spread_bps > 25:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.FUTURES,
                symbol=snapshot.symbol,
                reason=f"期货价差过大 {spread_bps:.1f} bps",
                confidence=0.5
            )
        
        # 订单流分析
        bid_vol = sum(q for _, q in ob.bids[:15])
        ask_vol = sum(q for _, q in ob.asks[:15])
        
        if bid_vol > ask_vol * 1.35:
            return TradeIntent(
                action=Action.BUY,
                market=Market.FUTURES,
                symbol=snapshot.symbol,
                quantity_pct=0.10,
                reason=f"期货买盘压力 (比例={bid_vol/ask_vol:.2f})",
                confidence=0.60
            )
        
        if ask_vol > bid_vol * 1.35:
            return TradeIntent(
                action=Action.SELL,
                market=Market.FUTURES,
                symbol=snapshot.symbol,
                quantity_pct=0.10,
                reason=f"期货卖盘压力 (比例={ask_vol/bid_vol:.2f})",
                confidence=0.60
            )
        
        return TradeIntent(
            action=Action.HOLD,
            market=Market.FUTURES,
            symbol=snapshot.symbol,
            reason="期货订单流平衡",
            confidence=0.5
        )


class SentimentAgent(BaseAgent):
    """
    情绪分析专家 Agent
    
    数据源：
    1. X/Twitter
    2. 新闻（NewsAPI、GDELT）
    3. 微信公众号
    4. 雪球
    5. Reddit
    """
    
    def __init__(self):
        super().__init__("sentiment")
        self._sentiment_cache: Dict[str, float] = {}  # symbol -> sentiment_score
    
    async def run(self, snapshot: MarketSnapshot, context: str) -> TradeIntent:
        """情绪分析"""
        # 获取情绪分数（-1 到 1）
        sentiment_score = self._get_sentiment_score(snapshot.symbol, context)
        
        if sentiment_score is None:
            return TradeIntent(
                action=Action.HOLD,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                reason="情绪数据不可用",
                confidence=0.0
            )
        
        # 根据情绪分数决策
        if sentiment_score > 0.6:
            # 强烈正面情绪
            return TradeIntent(
                action=Action.BUY,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.08,
                reason=f"市场情绪极度乐观 (score={sentiment_score:.2f})",
                confidence=0.5 + 0.2 * sentiment_score,
                metadata={"sentiment_score": sentiment_score}
            )
        
        elif sentiment_score < -0.6:
            # 强烈负面情绪
            return TradeIntent(
                action=Action.SELL,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.08,
                reason=f"市场情绪极度悲观 (score={sentiment_score:.2f})",
                confidence=0.5 + 0.2 * abs(sentiment_score),
                metadata={"sentiment_score": sentiment_score}
            )
        
        elif 0.3 < sentiment_score < 0.6:
            # 中度正面
            return TradeIntent(
                action=Action.BUY,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.05,
                reason=f"市场情绪偏乐观 (score={sentiment_score:.2f})",
                confidence=0.55,
                metadata={"sentiment_score": sentiment_score}
            )
        
        elif -0.6 < sentiment_score < -0.3:
            # 中度负面
            return TradeIntent(
                action=Action.SELL,
                market=Market.CRYPTO,
                symbol=snapshot.symbol,
                quantity_pct=0.05,
                reason=f"市场情绪偏悲观 (score={sentiment_score:.2f})",
                confidence=0.55,
                metadata={"sentiment_score": sentiment_score}
            )
        
        return TradeIntent(
            action=Action.HOLD,
            market=Market.CRYPTO,
            symbol=snapshot.symbol,
            reason=f"市场情绪中性 (score={sentiment_score:.2f})",
            confidence=0.5,
            metadata={"sentiment_score": sentiment_score}
        )
    
    def _get_sentiment_score(self, symbol: str, context: str) -> Optional[float]:
        """
        获取情绪分数
        
        简化实现：从 context 解析
        实际应该调用情绪分析API或模型
        
        Returns:
            -1 到 1 的情绪分数
        """
        # 检查缓存
        if symbol in self._sentiment_cache:
            return self._sentiment_cache[symbol]
        
        # 从 context 解析（简化）
        if "sentiment" in context.lower():
            try:
                # 示例：context 包含 "sentiment: 0.75"
                parts = context.split("sentiment:")
                if len(parts) > 1:
                    score_str = parts[1].split()[0].strip()
                    score = float(score_str)
                    self._sentiment_cache[symbol] = score
                    return score
            except Exception:
                pass
        
        # 默认中性
        return 0.0
