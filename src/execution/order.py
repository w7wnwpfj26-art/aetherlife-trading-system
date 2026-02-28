"""
订单数据模型与订单管理器
统一表示市价单/限价单/止损单，跟踪订单全生命周期状态
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


# ──────────────────────────────────────────────
# 枚举定义
# ──────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET     = "MARKET"
    LIMIT      = "LIMIT"
    STOP_LOSS  = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(str, Enum):
    PENDING          = "PENDING"           # 已创建，未提交
    SUBMITTED        = "SUBMITTED"         # 已提交交易所
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    FILLED           = "FILLED"            # 完全成交
    CANCELLED        = "CANCELLED"         # 已撤销
    REJECTED         = "REJECTED"          # 被拒绝
    FAILED           = "FAILED"            # 系统错误


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class Order:
    """完整订单模型"""

    # 标识
    order_id: str = field(default_factory=lambda: f"ORD_{uuid.uuid4().hex[:10].upper()}")
    client_order_id: Optional[str] = None   # 本地自定义 ID，用于幂等对账
    exchange_order_id: Optional[str] = None # 交易所返回的订单号

    # 订单参数
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0          # 委托数量
    price: float = 0.0             # 委托价格（市价单可为 0）
    stop_price: float = 0.0        # 止损触发价
    reduce_only: bool = False
    leverage: int = 1

    # 状态
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0   # 已成交数量
    average_price: float = 0.0     # 成交均价
    commission: float = 0.0        # 手续费
    slippage: float = 0.0          # 滑点

    # 时间
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # 附加信息
    error_message: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)  # 自定义标签，如 {"reason": "stop_loss"}

    # ── 便捷属性 ──────────────────────────────────
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def realized_pnl(self) -> float:
        """成交金额（不含手续费）"""
        if self.average_price <= 0:
            return 0.0
        return self.filled_quantity * self.average_price

    def to_dict(self) -> Dict:
        return {
            "order_id":          self.order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol":            self.symbol,
            "side":              self.side.value,
            "type":              self.order_type.value,
            "quantity":          self.quantity,
            "price":             self.price,
            "status":            self.status.value,
            "filled_qty":        self.filled_quantity,
            "avg_price":         self.average_price,
            "commission":        self.commission,
            "created_at":        self.created_at.isoformat(),
            "error":             self.error_message,
        }

    def __repr__(self) -> str:
        return (
            f"Order({self.order_id} {self.side.value} {self.quantity} {self.symbol} "
            f"@ {self.price or 'MKT'} [{self.status.value}])"
        )


# ──────────────────────────────────────────────
# 订单管理器
# ──────────────────────────────────────────────

class OrderManager:
    """
    内存订单管理器
    负责创建、更新、查询订单；可作为 TradingBot 的订单账本
    """

    def __init__(self, max_completed: int = 2000):
        self._active: Dict[str, Order] = {}      # order_id → Order
        self._completed: List[Order] = []
        self._max_completed = max_completed

    # ── 创建 ──────────────────────────────────────
    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        leverage: int = 1,
        reduce_only: bool = False,
        **tags,
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            leverage=leverage,
            reduce_only=reduce_only,
            tags=dict(tags),
        )
        self._active[order.order_id] = order
        return order

    def create_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        leverage: int = 1,
        reduce_only: bool = False,
        **tags,
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            leverage=leverage,
            reduce_only=reduce_only,
            tags=dict(tags),
        )
        self._active[order.order_id] = order
        return order

    # ── 状态更新 ──────────────────────────────────
    def mark_submitted(self, order_id: str, exchange_order_id: str = "") -> Optional[Order]:
        order = self._active.get(order_id)
        if order:
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.utcnow()
            if exchange_order_id:
                order.exchange_order_id = exchange_order_id
        return order

    def mark_filled(
        self,
        order_id: str,
        filled_quantity: float,
        average_price: float,
        commission: float = 0.0,
    ) -> Optional[Order]:
        order = self._active.get(order_id)
        if order is None:
            return None
        order.filled_quantity = filled_quantity
        order.average_price = average_price
        order.commission = commission
        order.filled_at = datetime.utcnow()
        order.status = (
            OrderStatus.FILLED
            if filled_quantity >= order.quantity * 0.999  # 允许微小误差
            else OrderStatus.PARTIALLY_FILLED
        )
        if order.status == OrderStatus.FILLED:
            self._complete(order_id)
        return order

    def mark_cancelled(self, order_id: str, reason: str = "") -> Optional[Order]:
        order = self._active.get(order_id)
        if order:
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.utcnow()
            if reason:
                order.error_message = reason
            self._complete(order_id)
        return order

    def mark_failed(self, order_id: str, error: str) -> Optional[Order]:
        order = self._active.get(order_id)
        if order:
            order.status = OrderStatus.FAILED
            order.error_message = error
            self._complete(order_id)
        return order

    # ── 查询 ──────────────────────────────────────
    def get(self, order_id: str) -> Optional[Order]:
        return self._active.get(order_id) or next(
            (o for o in reversed(self._completed) if o.order_id == order_id), None
        )

    def get_active(self, symbol: Optional[str] = None) -> List[Order]:
        orders = list(self._active.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_completed(self, symbol: Optional[str] = None, limit: int = 100) -> List[Order]:
        orders = self._completed[-limit:]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_stats(self) -> Dict:
        total = len(self._completed)
        filled  = [o for o in self._completed if o.status == OrderStatus.FILLED]
        failed  = [o for o in self._completed if o.status == OrderStatus.FAILED]
        total_commission = sum(o.commission for o in filled)
        return {
            "active_orders":    len(self._active),
            "completed_orders": total,
            "filled":           len(filled),
            "failed":           len(failed),
            "success_rate":     len(filled) / total * 100 if total else 0.0,
            "total_commission": total_commission,
        }

    # ── 内部 ──────────────────────────────────────
    def _complete(self, order_id: str) -> None:
        order = self._active.pop(order_id, None)
        if order:
            self._completed.append(order)
            # 防止内存无限增长
            if len(self._completed) > self._max_completed:
                self._completed = self._completed[-self._max_completed:]
