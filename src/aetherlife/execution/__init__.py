"""
执行层（Execution Layer）

统一订单执行接口：
- 智能路由（SmartRouter）：选择最优交易所和订单类型
- 订单拆分（OrderSplitter）：TWAP/VWAP/Iceberg拆分策略
- 执行引擎（OrderExecutionEngine）：统一多交易所执行
"""

from .smart_router import (
    SmartRouter,
    RoutingDecision,
    Exchange,
    OrderType,
    LiquidityProvider
)

from .order_splitter import (
    OrderSplitter,
    SubOrder,
    SplitStrategy
)

from .order_executor import (
    OrderExecutionEngine,
    ExecutionResult,
    OrderStatus
)

__all__ = [
    # Smart Router
    "SmartRouter",
    "RoutingDecision",
    "Exchange",
    "OrderType",
    "LiquidityProvider",
    
    # Order Splitter
    "OrderSplitter",
    "SubOrder",
    "SplitStrategy",
    
    # Order Executor
    "OrderExecutionEngine",
    "ExecutionResult",
    "OrderStatus"
]
