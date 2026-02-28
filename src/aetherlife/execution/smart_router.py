"""
智能路由器（Smart Router）

根据交易意图自动选择最优交易所和订单类型：
- 加密货币 → Binance/Bybit（选择流动性更好的）
- A股 → IBKR Stock Connect
- 美股/港股/外汇/期货 → IBKR
- 自动选择订单类型（MARKET/LIMIT/FOK/IOC/POST_ONLY）
- 估算滑点和手续费
"""

from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
import asyncio

from ..cognition.schemas import TradeIntent, Market, Action


class Exchange(str, Enum):
    """交易所枚举"""
    IBKR = "IBKR"
    BINANCE = "BINANCE"
    BYBIT = "BYBIT"
    OKX = "OKX"


class OrderType(str, Enum):
    """订单类型枚举"""
    MARKET = "MARKET"          # 市价单
    LIMIT = "LIMIT"            # 限价单
    FOK = "FOK"                # Fill-Or-Kill（全成交或全取消）
    IOC = "IOC"                # Immediate-Or-Cancel（立即成交或取消）
    POST_ONLY = "POST_ONLY"    # 只做Maker（挂单）


@dataclass
class RoutingDecision:
    """路由决策"""
    exchange: Exchange
    order_type: OrderType
    split_orders: List[Dict[str, Any]]  # 拆分后的订单列表
    estimated_slippage: float
    estimated_fee: float
    estimated_total_cost: float
    reason: str  # 选择该路由的原因


class SmartRouter:
    """
    智能路由器
    
    核心功能：
    1. 根据市场类型选择交易所
    2. 根据订单大小和紧急程度选择订单类型
    3. 评估流动性，选择最优交易所
    4. 估算滑点和手续费
    """
    
    def __init__(
        self,
        # 手续费率配置
        fee_rates: Optional[Dict[Exchange, float]] = None,
        # 滑点率配置（基础滑点）
        slippage_rates: Optional[Dict[Exchange, float]] = None,
        # 流动性数据（订单簿深度）
        liquidity_provider=None,
        verbose: int = 1
    ):
        """
        初始化智能路由器
        
        Args:
            fee_rates: 各交易所手续费率
            slippage_rates: 各交易所基础滑点率
            liquidity_provider: 流动性数据提供者（用于查询订单簿）
            verbose: 日志详细程度
        """
        # 默认手续费率
        self.fee_rates = fee_rates or {
            Exchange.IBKR: 0.0005,      # 0.05%
            Exchange.BINANCE: 0.001,    # 0.1%（Taker）
            Exchange.BYBIT: 0.001,      # 0.1%（Taker）
            Exchange.OKX: 0.001         # 0.1%（Taker）
        }
        
        # 默认滑点率
        self.slippage_rates = slippage_rates or {
            Exchange.IBKR: 0.0005,
            Exchange.BINANCE: 0.0003,
            Exchange.BYBIT: 0.0003,
            Exchange.OKX: 0.0004
        }
        
        self.liquidity_provider = liquidity_provider
        self.verbose = verbose
    
    def route(self, intent: TradeIntent, balance: float = 10000) -> RoutingDecision:
        """
        路由交易意图
        
        Args:
            intent: 交易意图
            balance: 账户余额
        
        Returns:
            路由决策
        """
        # 1. 根据市场类型选择交易所
        exchange = self._select_exchange(intent.market, intent.symbol)
        
        # 2. 根据订单特征选择订单类型
        order_size_usd = balance * intent.quantity_pct
        order_type = self._select_order_type(
            intent.action,
            order_size_usd,
            intent.confidence,
            exchange
        )
        
        # 3. 估算成本
        estimated_slippage = self._estimate_slippage(
            intent.symbol,
            order_size_usd,
            exchange
        )
        estimated_fee = order_size_usd * self.fee_rates[exchange]
        estimated_total_cost = estimated_slippage + estimated_fee
        
        # 4. 决定是否拆分订单
        split_orders = self._split_order_if_needed(
            intent,
            order_size_usd,
            exchange
        )
        
        # 5. 生成决策
        reason = self._generate_reason(
            intent, exchange, order_type, estimated_slippage, estimated_fee
        )
        
        decision = RoutingDecision(
            exchange=exchange,
            order_type=order_type,
            split_orders=split_orders,
            estimated_slippage=estimated_slippage,
            estimated_fee=estimated_fee,
            estimated_total_cost=estimated_total_cost,
            reason=reason
        )
        
        if self.verbose >= 1:
            print(f"[SmartRouter] {intent.symbol} → {exchange.value}")
            print(f"  订单类型: {order_type.value}")
            print(f"  预估滑点: {estimated_slippage:.2f} USD")
            print(f"  预估手续费: {estimated_fee:.2f} USD")
            print(f"  拆分订单数: {len(split_orders)}")
        
        return decision
    
    def _select_exchange(self, market: Market, symbol: str) -> Exchange:
        """
        根据市场类型选择交易所
        
        优先级规则：
        - 加密货币 → Binance/Bybit（选择流动性更好的）
        - A股 → IBKR Stock Connect
        - 美股/港股/外汇/期货 → IBKR
        """
        if market == Market.CRYPTO:
            # 加密货币：比较Binance和Bybit的流动性
            return self._select_crypto_exchange(symbol)
        
        # 其他市场全部走IBKR
        return Exchange.IBKR
    
    def _select_crypto_exchange(self, symbol: str) -> Exchange:
        """
        选择加密货币交易所
        
        比较Binance和Bybit的流动性（订单簿深度）
        """
        if self.liquidity_provider is None:
            # 没有流动性数据，默认Binance
            return Exchange.BINANCE
        
        # 查询两个交易所的订单簿深度
        binance_depth = self.liquidity_provider.get_depth(Exchange.BINANCE, symbol)
        bybit_depth = self.liquidity_provider.get_depth(Exchange.BYBIT, symbol)
        
        # 简单比较：总深度（bid + ask）
        binance_total = binance_depth.get("total_volume", 0)
        bybit_total = bybit_depth.get("total_volume", 0)
        
        if binance_total > bybit_total:
            return Exchange.BINANCE
        else:
            return Exchange.BYBIT
    
    def _select_order_type(
        self,
        action: Action,
        order_size_usd: float,
        confidence: float,
        exchange: Exchange
    ) -> OrderType:
        """
        选择订单类型
        
        规则：
        1. 小单 + 高置信度 → MARKET（快速成交）
        2. 大单 + 低紧急度 → LIMIT（减少滑点）
        3. 中等单 + 做市需求 → POST_ONLY（吃返佣）
        4. 紧急平仓 → FOK（全成交或全取消）
        """
        # 判断订单大小
        is_small_order = order_size_usd < 1000
        is_large_order = order_size_usd > 5000
        
        # 判断紧急程度（高置信度 = 高紧急度）
        is_urgent = confidence > 0.8
        
        # 判断是否平仓
        is_close = action == Action.CLOSE
        
        # 规则引擎
        if is_close and is_urgent:
            return OrderType.FOK  # 紧急平仓，全成交或全取消
        
        if is_small_order and is_urgent:
            return OrderType.MARKET  # 小单快速成交
        
        if is_large_order:
            return OrderType.LIMIT  # 大单用限价单减少滑点
        
        # 默认：中等单用POST_ONLY做市
        return OrderType.POST_ONLY
    
    def _estimate_slippage(
        self,
        symbol: str,
        order_size_usd: float,
        exchange: Exchange
    ) -> float:
        """
        估算滑点
        
        滑点 = 基础滑点 × 订单大小因子 × 市场波动因子
        """
        base_slippage = self.slippage_rates[exchange]
        
        # 订单大小因子（每增加1000 USD，滑点增加10%）
        size_factor = 1.0 + (order_size_usd / 1000) * 0.1
        
        # 市场波动因子（简化：假设固定为1.0，实际应根据ATR计算）
        volatility_factor = 1.0
        
        # 估算滑点金额
        estimated_slippage_pct = base_slippage * size_factor * volatility_factor
        estimated_slippage_usd = order_size_usd * estimated_slippage_pct
        
        return estimated_slippage_usd
    
    def _split_order_if_needed(
        self,
        intent: TradeIntent,
        order_size_usd: float,
        exchange: Exchange
    ) -> List[Dict[str, Any]]:
        """
        判断是否需要拆分订单
        
        规则：
        - 大单（>5000 USD）拆分为多个小单
        - 减少市场冲击
        """
        max_order_size = 2000  # 每个子订单最大2000 USD
        
        if order_size_usd <= max_order_size:
            # 不需要拆分
            return [{
                "symbol": intent.symbol,
                "action": intent.action.value,
                "quantity_pct": intent.quantity_pct,
                "order_type": None  # 将在route中填充
            }]
        
        # 需要拆分
        n_splits = int(order_size_usd / max_order_size) + 1
        quantity_per_split = intent.quantity_pct / n_splits
        
        split_orders = []
        for i in range(n_splits):
            split_orders.append({
                "symbol": intent.symbol,
                "action": intent.action.value,
                "quantity_pct": quantity_per_split,
                "order_type": None,
                "split_index": i + 1,
                "total_splits": n_splits
            })
        
        return split_orders
    
    def _generate_reason(
        self,
        intent: TradeIntent,
        exchange: Exchange,
        order_type: OrderType,
        estimated_slippage: float,
        estimated_fee: float
    ) -> str:
        """生成路由决策的原因"""
        reasons = []
        
        # 交易所选择原因
        if intent.market == Market.CRYPTO:
            reasons.append(f"加密货币交易，选择{exchange.value}（流动性最优）")
        elif intent.market == Market.A_STOCK:
            reasons.append(f"A股交易，通过IBKR Stock Connect")
        else:
            reasons.append(f"{intent.market.value}交易，使用IBKR")
        
        # 订单类型选择原因
        if order_type == OrderType.MARKET:
            reasons.append("小单高置信度，使用市价单快速成交")
        elif order_type == OrderType.LIMIT:
            reasons.append("大单，使用限价单减少滑点")
        elif order_type == OrderType.POST_ONLY:
            reasons.append("中等单，使用POST_ONLY做市吃返佣")
        elif order_type == OrderType.FOK:
            reasons.append("紧急平仓，使用FOK全成交或全取消")
        
        # 成本信息
        reasons.append(f"预估总成本: {estimated_slippage + estimated_fee:.2f} USD")
        
        return "; ".join(reasons)
    
    async def route_batch(
        self,
        intents: List[TradeIntent],
        balance: float = 10000
    ) -> List[RoutingDecision]:
        """
        批量路由（并行）
        
        Args:
            intents: 交易意图列表
            balance: 账户余额
        
        Returns:
            路由决策列表
        """
        tasks = [self._route_async(intent, balance) for intent in intents]
        return await asyncio.gather(*tasks)
    
    async def _route_async(self, intent: TradeIntent, balance: float) -> RoutingDecision:
        """异步路由（用于批量并行）"""
        # route方法本身是同步的，这里只是包装为async
        return self.route(intent, balance)


class LiquidityProvider:
    """
    流动性数据提供者（Mock）
    
    实际应用中应连接到实时订单簿数据源
    """
    
    def __init__(self):
        # Mock数据：交易所 → 品种 → 流动性指标
        self.depth_cache = {
            Exchange.BINANCE: {
                "BTCUSDT": {"total_volume": 1000.0, "bid_depth": 500.0, "ask_depth": 500.0},
                "ETHUSDT": {"total_volume": 800.0, "bid_depth": 400.0, "ask_depth": 400.0}
            },
            Exchange.BYBIT: {
                "BTCUSDT": {"total_volume": 900.0, "bid_depth": 450.0, "ask_depth": 450.0},
                "ETHUSDT": {"total_volume": 700.0, "bid_depth": 350.0, "ask_depth": 350.0}
            }
        }
    
    def get_depth(self, exchange: Exchange, symbol: str) -> Dict[str, float]:
        """获取订单簿深度"""
        return self.depth_cache.get(exchange, {}).get(symbol, {
            "total_volume": 0,
            "bid_depth": 0,
            "ask_depth": 0
        })
    
    def update_depth(self, exchange: Exchange, symbol: str, depth_data: Dict):
        """更新订单簿深度（从WebSocket实时更新）"""
        if exchange not in self.depth_cache:
            self.depth_cache[exchange] = {}
        self.depth_cache[exchange][symbol] = depth_data


if __name__ == "__main__":
    # 示例：智能路由
    from aetherlife.cognition.schemas import TradeIntent, Action, Market
    
    # 创建路由器
    liquidity_provider = LiquidityProvider()
    router = SmartRouter(liquidity_provider=liquidity_provider, verbose=1)
    
    # 测试1：加密货币小单
    intent1 = TradeIntent(
        action=Action.BUY,
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        quantity_pct=0.05,  # 5%仓位
        confidence=0.9
    )
    
    decision1 = router.route(intent1, balance=10000)
    print(f"\n决策1: {decision1.exchange.value} - {decision1.order_type.value}")
    print(f"原因: {decision1.reason}")
    
    # 测试2：A股大单
    intent2 = TradeIntent(
        action=Action.BUY,
        market=Market.A_STOCK,
        symbol="600519",
        quantity_pct=0.6,  # 60%仓位（大单）
        confidence=0.6
    )
    
    decision2 = router.route(intent2, balance=10000)
    print(f"\n决策2: {decision2.exchange.value} - {decision2.order_type.value}")
    print(f"拆分订单数: {len(decision2.split_orders)}")
    print(f"原因: {decision2.reason}")
    
    # 测试3：紧急平仓
    intent3 = TradeIntent(
        action=Action.CLOSE,
        market=Market.CRYPTO,
        symbol="ETHUSDT",
        quantity_pct=1.0,
        confidence=0.95
    )
    
    decision3 = router.route(intent3, balance=10000)
    print(f"\n决策3: {decision3.exchange.value} - {decision3.order_type.value}")
    print(f"原因: {decision3.reason}")
