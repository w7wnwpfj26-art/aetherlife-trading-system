"""
订单执行引擎（Order Execution Engine）

统一封装多交易所的订单执行接口：
- 支持 IBKR/Binance/Bybit/OKX
- 自动重试和错误处理
- 订单状态跟踪
- 执行结果报告
"""

from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import uuid
import sys
import os

# 将 src 根目录加入路径，使 execution.retry 可正常导入
_src_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

try:
    from execution.retry import retry_async  # 复用指数退避重试
except ImportError:
    retry_async = None  # 降级：若导入失败则使用内置简单重试

from .smart_router import Exchange, OrderType, RoutingDecision
from .order_splitter import SubOrder


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"            # 待执行
    SUBMITTED = "SUBMITTED"        # 已提交
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    FILLED = "FILLED"              # 完全成交
    CANCELLED = "CANCELLED"        # 已取消
    REJECTED = "REJECTED"          # 被拒绝
    FAILED = "FAILED"              # 失败


@dataclass
class ExecutionResult:
    """执行结果"""
    order_id: str
    exchange: Exchange
    symbol: str
    action: str
    status: OrderStatus
    
    # 执行信息
    requested_quantity: float
    filled_quantity: float = 0.0
    average_price: float = 0.0
    
    # 成本信息
    commission: float = 0.0
    slippage: float = 0.0
    total_cost: float = 0.0
    
    # 时间信息
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderExecutionEngine:
    """
    订单执行引擎
    
    核心功能：
    1. 统一多交易所订单执行接口
    2. 自动重试和错误处理
    3. 订单状态跟踪
    4. 执行结果统计
    """
    
    def __init__(
        self,
        # 交易所连接器（需要从外部注入）
        ibkr_connector=None,
        binance_connector=None,
        bybit_connector=None,
        okx_connector=None,
        
        # 重试配置
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        
        # 执行配置
        enable_dry_run: bool = False,  # 模拟执行（不实际下单）
        
        verbose: int = 1
    ):
        """
        初始化执行引擎
        
        Args:
            *_connector: 各交易所连接器
            max_retries: 最大重试次数
            retry_delay_seconds: 重试延迟
            enable_dry_run: 是否模拟执行
            verbose: 日志详细程度
        """
        self.connectors = {
            Exchange.IBKR: ibkr_connector,
            Exchange.BINANCE: binance_connector,
            Exchange.BYBIT: bybit_connector,
            Exchange.OKX: okx_connector
        }
        
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.enable_dry_run = enable_dry_run
        self.verbose = verbose
        
        # 订单跟踪
        self.active_orders: Dict[str, ExecutionResult] = {}
        self.completed_orders: List[ExecutionResult] = []
    
    async def execute(
        self,
        routing_decision: RoutingDecision,
        callback: Optional[Callable] = None
    ) -> List[ExecutionResult]:
        """
        执行路由决策
        
        Args:
            routing_decision: 智能路由决策
            callback: 执行完成后的回调函数
        
        Returns:
            执行结果列表（如果有拆分订单，返回多个结果）
        """
        results = []
        
        # 遍历所有子订单
        for split_order in routing_decision.split_orders:
            result = await self._execute_single_order(
                exchange=routing_decision.exchange,
                order_type=routing_decision.order_type,
                split_order=split_order
            )
            results.append(result)
            
            # 如果执行失败，立即停止后续订单
            if result.status in [OrderStatus.REJECTED, OrderStatus.FAILED]:
                if self.verbose >= 1:
                    print(f"[ExecutionEngine] 订单失败，停止后续执行: {result.error_message}")
                break
        
        # 回调
        if callback:
            await callback(results)
        
        return results
    
    async def _execute_single_order(
        self,
        exchange: Exchange,
        order_type: OrderType,
        split_order: Dict[str, Any]
    ) -> ExecutionResult:
        """
        执行单个子订单
        
        Args:
            exchange: 交易所
            order_type: 订单类型
            split_order: 子订单信息
        
        Returns:
            执行结果
        """
        order_id = self._generate_order_id()
        symbol = split_order["symbol"]
        action = split_order["action"]
        quantity_pct = split_order["quantity_pct"]
        
        # 创建执行结果对象
        result = ExecutionResult(
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            action=action,
            status=OrderStatus.PENDING,
            requested_quantity=quantity_pct,
            submitted_at=datetime.now()
        )
        
        # 添加到活跃订单
        self.active_orders[order_id] = result
        
        # 获取连接器
        connector = self.connectors.get(exchange)
        if connector is None:
            result.status = OrderStatus.FAILED
            result.error_message = f"交易所连接器未配置: {exchange.value}"
            self._mark_completed(order_id)
            return result
        
        # 执行订单（指数退避重试）
        if self.enable_dry_run:
            # 模拟执行，直接成功
            await asyncio.sleep(0.05)
            result.status = OrderStatus.FILLED
            result.filled_quantity = quantity_pct
            result.average_price = 50000.0  # Mock 价格
            result.commission = result.filled_quantity * result.average_price * 0.001
            result.filled_at = datetime.now()
            if self.verbose >= 1:
                print(f"[DRY RUN] {order_id}: {action} {quantity_pct:.4f} {symbol} @ {exchange.value}")
        else:
            try:
                # 使用 retry_async 实现指数退避，base_delay 为初始等待时间
                if retry_async is not None:
                    filled_result = await retry_async(
                        self._submit_to_exchange,
                        connector, symbol, action, quantity_pct, order_type,
                        max_retries=self.max_retries,
                        base_delay=self.retry_delay_seconds,
                        max_delay=self.retry_delay_seconds * 8,
                        backoff_factor=2.0,
                    )
                else:
                    # 降级：简单固定延迟重试
                    filled_result = None
                    for attempt in range(self.max_retries):
                        try:
                            filled_result = await self._submit_to_exchange(
                                connector, symbol, action, quantity_pct, order_type
                            )
                            break
                        except Exception:
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(self.retry_delay_seconds)
                            else:
                                raise

                result.status = OrderStatus.FILLED
                result.filled_quantity = filled_result["filled_quantity"]
                result.average_price = filled_result["average_price"]
                result.commission = filled_result["commission"]
                result.filled_at = datetime.now()
                if self.verbose >= 1:
                    print(f"[ExecutionEngine] {order_id}: 成交 {result.filled_quantity:.4f} @ ${result.average_price:.2f}")
            except Exception as e:
                result.status = OrderStatus.FAILED
                result.error_message = f"执行失败（已重试 {self.max_retries} 次）: {e}"
                if self.verbose >= 1:
                    print(f"[ExecutionEngine] {result.error_message}")
        
        # 标记为已完成
        self._mark_completed(order_id)
        
        return result
    
    async def _submit_to_exchange(
        self,
        connector: Any,
        symbol: str,
        action: str,
        quantity: float,
        order_type: OrderType
    ) -> Dict[str, Any]:
        """
        提交订单到交易所
        
        Args:
            connector: 交易所连接器
            symbol: 品种
            action: 动作
            quantity: 数量
            order_type: 订单类型
        
        Returns:
            成交信息
        """
        # 这里应该调用连接器的实际方法
        # 由于各交易所API不同，这里只是示例
        
        if hasattr(connector, "place_order"):
            return await connector.place_order(
                symbol=symbol,
                side=action.lower(),
                quantity=quantity,
                order_type=order_type.value
            )
        else:
            raise NotImplementedError(f"连接器未实现place_order方法")
    
    def _generate_order_id(self) -> str:
        """生成订单ID"""
        return f"ORDER_{uuid.uuid4().hex[:12].upper()}"
    
    def _mark_completed(self, order_id: str):
        """标记订单为已完成"""
        if order_id in self.active_orders:
            result = self.active_orders.pop(order_id)
            self.completed_orders.append(result)
    
    def get_active_orders(self) -> List[ExecutionResult]:
        """获取活跃订单"""
        return list(self.active_orders.values())
    
    def get_completed_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[Exchange] = None,
        limit: int = 100
    ) -> List[ExecutionResult]:
        """
        获取已完成订单
        
        Args:
            symbol: 过滤品种
            exchange: 过滤交易所
            limit: 返回数量限制
        
        Returns:
            已完成订单列表
        """
        orders = self.completed_orders
        
        # 过滤
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        if exchange:
            orders = [o for o in orders if o.exchange == exchange]
        
        # 限制数量（返回最近的N个）
        return orders[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取执行统计
        
        Returns:
            统计数据
        """
        total_orders = len(self.completed_orders)
        
        if total_orders == 0:
            return {
                "total_orders": 0,
                "filled_orders": 0,
                "failed_orders": 0,
                "success_rate": 0.0,
                "average_commission": 0.0,
                "average_slippage": 0.0
            }
        
        filled_orders = [o for o in self.completed_orders if o.status == OrderStatus.FILLED]
        failed_orders = [o for o in self.completed_orders if o.status == OrderStatus.FAILED]
        
        total_commission = sum(o.commission for o in filled_orders)
        total_slippage = sum(o.slippage for o in filled_orders)
        
        return {
            "total_orders": total_orders,
            "filled_orders": len(filled_orders),
            "failed_orders": len(failed_orders),
            "success_rate": len(filled_orders) / total_orders * 100,
            "average_commission": total_commission / len(filled_orders) if filled_orders else 0,
            "average_slippage": total_slippage / len(filled_orders) if filled_orders else 0,
            "total_commission": total_commission,
            "total_slippage": total_slippage
        }
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
        
        Returns:
            是否成功取消
        """
        if order_id not in self.active_orders:
            return False
        
        result = self.active_orders[order_id]
        result.status = OrderStatus.CANCELLED
        self._mark_completed(order_id)
        
        if self.verbose >= 1:
            print(f"[ExecutionEngine] 订单已取消: {order_id}")
        
        return True


if __name__ == "__main__":
    # 示例：订单执行
    
    async def main():
        # 创建执行引擎（模拟模式）
        engine = OrderExecutionEngine(
            enable_dry_run=True,
            verbose=1
        )
        
        # 模拟路由决策
        from aetherlife.execution.smart_router import RoutingDecision, Exchange, OrderType
        
        decision = RoutingDecision(
            exchange=Exchange.BINANCE,
            order_type=OrderType.MARKET,
            split_orders=[
                {"symbol": "BTCUSDT", "action": "BUY", "quantity_pct": 0.05},
                {"symbol": "BTCUSDT", "action": "BUY", "quantity_pct": 0.05}
            ],
            estimated_slippage=5.0,
            estimated_fee=10.0,
            estimated_total_cost=15.0,
            reason="测试执行"
        )
        
        # 执行
        results = await engine.execute(decision)
        
        # 打印结果
        print("\n=== 执行结果 ===")
        for result in results:
            print(f"{result.order_id}:")
            print(f"  状态: {result.status.value}")
            print(f"  成交: {result.filled_quantity:.4f}")
            print(f"  均价: ${result.average_price:.2f}")
            print(f"  手续费: ${result.commission:.2f}")
        
        # 获取统计
        stats = engine.get_statistics()
        print("\n=== 执行统计 ===")
        print(f"总订单数: {stats['total_orders']}")
        print(f"成功率: {stats['success_rate']:.2f}%")
        print(f"平均手续费: ${stats['average_commission']:.2f}")
    
    # 运行
    asyncio.run(main())
