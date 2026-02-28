"""
订单拆分器（Order Splitter）

将大单拆分为多个小单，减少市场冲击：
- TWAP（Time-Weighted Average Price）：时间加权
- VWAP（Volume-Weighted Average Price）：成交量加权
- Iceberg Order：冰山订单（只显示部分数量）
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np


class SplitStrategy(str, Enum):
    """拆分策略枚举"""
    TWAP = "TWAP"          # 时间加权平均价格
    VWAP = "VWAP"          # 成交量加权平均价格
    ICEBERG = "ICEBERG"    # 冰山订单
    ADAPTIVE = "ADAPTIVE"  # 自适应拆分


@dataclass
class SubOrder:
    """子订单"""
    parent_order_id: str
    sub_order_id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: float
    price: Optional[float] = None  # None表示市价单
    execute_at: Optional[datetime] = None  # 执行时间
    order_type: str = "LIMIT"
    status: str = "PENDING"  # PENDING, FILLED, CANCELLED


class OrderSplitter:
    """
    订单拆分器
    
    核心功能：
    1. 根据市场流动性智能拆分
    2. 支持多种拆分策略（TWAP/VWAP/Iceberg）
    3. 减少市场冲击
    4. 优化执行成本
    """
    
    def __init__(
        self,
        max_order_size_usd: float = 2000,  # 单个子订单最大金额
        min_split_size: int = 2,            # 最小拆分数量
        max_split_size: int = 10,           # 最大拆分数量
        verbose: int = 1
    ):
        """
        初始化订单拆分器
        
        Args:
            max_order_size_usd: 单个子订单最大金额
            min_split_size: 最小拆分数量
            max_split_size: 最大拆分数量
            verbose: 日志详细程度
        """
        self.max_order_size_usd = max_order_size_usd
        self.min_split_size = min_split_size
        self.max_split_size = max_split_size
        self.verbose = verbose
        
        self._order_counter = 0  # 订单计数器
    
    def split(
        self,
        order_id: str,
        symbol: str,
        action: str,
        total_quantity: float,
        current_price: float,
        strategy: SplitStrategy = SplitStrategy.TWAP,
        duration_minutes: int = 60,
        market_volume_profile: Optional[List[float]] = None
    ) -> List[SubOrder]:
        """
        拆分订单
        
        Args:
            order_id: 父订单ID
            symbol: 交易品种
            action: 动作（BUY/SELL）
            total_quantity: 总数量
            current_price: 当前价格
            strategy: 拆分策略
            duration_minutes: 执行时长（分钟）
            market_volume_profile: 市场成交量分布（用于VWAP）
        
        Returns:
            子订单列表
        """
        total_value_usd = total_quantity * current_price
        
        # 判断是否需要拆分
        if total_value_usd <= self.max_order_size_usd:
            # 不需要拆分
            return [SubOrder(
                parent_order_id=order_id,
                sub_order_id=f"{order_id}_1",
                symbol=symbol,
                action=action,
                quantity=total_quantity,
                price=current_price,
                execute_at=datetime.now(),
                order_type="LIMIT"
            )]
        
        # 计算拆分数量
        n_splits = min(
            max(int(total_value_usd / self.max_order_size_usd), self.min_split_size),
            self.max_split_size
        )
        
        # 根据策略拆分
        if strategy == SplitStrategy.TWAP:
            return self._split_twap(
                order_id, symbol, action, total_quantity, current_price,
                n_splits, duration_minutes
            )
        elif strategy == SplitStrategy.VWAP:
            return self._split_vwap(
                order_id, symbol, action, total_quantity, current_price,
                n_splits, duration_minutes, market_volume_profile
            )
        elif strategy == SplitStrategy.ICEBERG:
            return self._split_iceberg(
                order_id, symbol, action, total_quantity, current_price,
                n_splits
            )
        elif strategy == SplitStrategy.ADAPTIVE:
            return self._split_adaptive(
                order_id, symbol, action, total_quantity, current_price,
                n_splits, duration_minutes
            )
        else:
            raise ValueError(f"未知的拆分策略: {strategy}")
    
    def _split_twap(
        self,
        order_id: str,
        symbol: str,
        action: str,
        total_quantity: float,
        current_price: float,
        n_splits: int,
        duration_minutes: int
    ) -> List[SubOrder]:
        """
        TWAP拆分：均匀分配时间
        
        例如：10个子订单，60分钟 → 每6分钟执行一个
        """
        sub_orders = []
        quantity_per_split = total_quantity / n_splits
        time_interval = duration_minutes / n_splits
        
        for i in range(n_splits):
            execute_at = datetime.now() + timedelta(minutes=i * time_interval)
            
            sub_orders.append(SubOrder(
                parent_order_id=order_id,
                sub_order_id=f"{order_id}_{i+1}",
                symbol=symbol,
                action=action,
                quantity=quantity_per_split,
                price=current_price,  # 实际执行时会更新为当时市价
                execute_at=execute_at,
                order_type="LIMIT"
            ))
        
        if self.verbose >= 1:
            print(f"[OrderSplitter] TWAP拆分: {n_splits}个子订单，每{time_interval:.1f}分钟执行1个")
        
        return sub_orders
    
    def _split_vwap(
        self,
        order_id: str,
        symbol: str,
        action: str,
        total_quantity: float,
        current_price: float,
        n_splits: int,
        duration_minutes: int,
        market_volume_profile: Optional[List[float]] = None
    ) -> List[SubOrder]:
        """
        VWAP拆分：按市场成交量分布分配
        
        例如：开盘和收盘时段成交量大，中间时段小
        """
        # 如果没有提供成交量分布，使用默认分布（U型：开盘和收盘高）
        if market_volume_profile is None:
            # 假设60分钟，前15分钟和后15分钟成交量大
            volume_profile = []
            for i in range(n_splits):
                t = i / n_splits
                if t < 0.25 or t > 0.75:
                    volume_profile.append(1.5)  # 开盘/收盘：1.5倍
                else:
                    volume_profile.append(0.8)  # 中间时段：0.8倍
        else:
            volume_profile = market_volume_profile[:n_splits]
        
        # 归一化成交量分布
        total_volume = sum(volume_profile)
        normalized_profile = [v / total_volume for v in volume_profile]
        
        # 按成交量分配数量
        sub_orders = []
        time_interval = duration_minutes / n_splits
        
        for i in range(n_splits):
            quantity = total_quantity * normalized_profile[i]
            execute_at = datetime.now() + timedelta(minutes=i * time_interval)
            
            sub_orders.append(SubOrder(
                parent_order_id=order_id,
                sub_order_id=f"{order_id}_{i+1}",
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=current_price,
                execute_at=execute_at,
                order_type="LIMIT"
            ))
        
        if self.verbose >= 1:
            print(f"[OrderSplitter] VWAP拆分: {n_splits}个子订单，按成交量分布分配")
        
        return sub_orders
    
    def _split_iceberg(
        self,
        order_id: str,
        symbol: str,
        action: str,
        total_quantity: float,
        current_price: float,
        n_splits: int
    ) -> List[SubOrder]:
        """
        Iceberg拆分：冰山订单（只显示部分数量）
        
        例如：10000股拆分为10个1000股，但市场只看到1000股
        """
        sub_orders = []
        quantity_per_split = total_quantity / n_splits
        
        for i in range(n_splits):
            # 所有子订单立即提交，但不公开总量
            sub_orders.append(SubOrder(
                parent_order_id=order_id,
                sub_order_id=f"{order_id}_iceberg_{i+1}",
                symbol=symbol,
                action=action,
                quantity=quantity_per_split,
                price=current_price,
                execute_at=datetime.now(),  # 立即执行
                order_type="POST_ONLY"  # 挂单，不主动吃单
            ))
        
        if self.verbose >= 1:
            print(f"[OrderSplitter] Iceberg拆分: {n_splits}个子订单，隐藏总量")
        
        return sub_orders
    
    def _split_adaptive(
        self,
        order_id: str,
        symbol: str,
        action: str,
        total_quantity: float,
        current_price: float,
        n_splits: int,
        duration_minutes: int
    ) -> List[SubOrder]:
        """
        Adaptive拆分：自适应拆分（根据市场实时情况动态调整）
        
        策略：
        - 前30%时间执行30%数量（快速建仓）
        - 中间40%时间执行40%数量（均匀执行）
        - 最后30%时间执行30%数量（收尾）
        """
        # 分段执行比例
        phase_ratios = [0.3, 0.4, 0.3]
        time_ratios = [0.3, 0.4, 0.3]
        
        sub_orders = []
        cumulative_quantity = 0
        cumulative_time = 0
        
        for phase_idx, (qty_ratio, time_ratio) in enumerate(zip(phase_ratios, time_ratios)):
            phase_quantity = total_quantity * qty_ratio
            phase_duration = duration_minutes * time_ratio
            phase_splits = max(int(n_splits * qty_ratio), 1)
            
            quantity_per_split = phase_quantity / phase_splits
            time_interval = phase_duration / phase_splits
            
            for i in range(phase_splits):
                execute_at = datetime.now() + timedelta(
                    minutes=cumulative_time + i * time_interval
                )
                
                sub_orders.append(SubOrder(
                    parent_order_id=order_id,
                    sub_order_id=f"{order_id}_adaptive_{len(sub_orders)+1}",
                    symbol=symbol,
                    action=action,
                    quantity=quantity_per_split,
                    price=current_price,
                    execute_at=execute_at,
                    order_type="LIMIT"
                ))
            
            cumulative_quantity += phase_quantity
            cumulative_time += phase_duration
        
        if self.verbose >= 1:
            print(f"[OrderSplitter] Adaptive拆分: {len(sub_orders)}个子订单，分3阶段执行")
        
        return sub_orders
    
    def estimate_impact(
        self,
        total_quantity: float,
        current_price: float,
        market_depth: float,
        n_splits: int
    ) -> Dict[str, float]:
        """
        估算市场冲击
        
        Args:
            total_quantity: 总数量
            current_price: 当前价格
            market_depth: 市场深度（订单簿总量）
            n_splits: 拆分数量
        
        Returns:
            市场冲击指标
        """
        # 市场冲击模型（简化）：
        # impact = sqrt(quantity / market_depth) * volatility
        
        total_value = total_quantity * current_price
        quantity_per_split = total_quantity / n_splits
        
        # 不拆分的冲击
        impact_no_split = np.sqrt(total_quantity / market_depth) * 0.01
        
        # 拆分后的冲击（假设线性降低）
        impact_with_split = np.sqrt(quantity_per_split / market_depth) * 0.01
        
        # 冲击成本（百分比）
        cost_no_split = impact_no_split * total_value
        cost_with_split = impact_with_split * total_value * n_splits
        
        return {
            "impact_no_split_pct": impact_no_split,
            "impact_with_split_pct": impact_with_split,
            "cost_no_split_usd": cost_no_split,
            "cost_with_split_usd": cost_with_split,
            "cost_reduction": cost_no_split - cost_with_split,
            "cost_reduction_pct": (cost_no_split - cost_with_split) / cost_no_split * 100
        }


if __name__ == "__main__":
    # 示例：订单拆分
    
    splitter = OrderSplitter(max_order_size_usd=2000, verbose=1)
    
    # 测试1：TWAP拆分
    print("\n=== 测试1：TWAP拆分 ===")
    sub_orders_twap = splitter.split(
        order_id="ORDER_001",
        symbol="BTCUSDT",
        action="BUY",
        total_quantity=0.2,  # 0.2 BTC
        current_price=50000,  # $50,000
        strategy=SplitStrategy.TWAP,
        duration_minutes=60
    )
    
    print(f"拆分为 {len(sub_orders_twap)} 个子订单:")
    for order in sub_orders_twap[:3]:  # 只打印前3个
        print(f"  {order.sub_order_id}: {order.quantity:.4f} @ {order.execute_at.strftime('%H:%M:%S')}")
    
    # 测试2：VWAP拆分
    print("\n=== 测试2：VWAP拆分 ===")
    sub_orders_vwap = splitter.split(
        order_id="ORDER_002",
        symbol="600519",
        action="BUY",
        total_quantity=1000,  # 1000股
        current_price=1800,  # ¥1800
        strategy=SplitStrategy.VWAP,
        duration_minutes=120
    )
    
    print(f"拆分为 {len(sub_orders_vwap)} 个子订单:")
    for order in sub_orders_vwap[:3]:
        print(f"  {order.sub_order_id}: {order.quantity:.0f}股 @ {order.execute_at.strftime('%H:%M:%S')}")
    
    # 测试3：市场冲击估算
    print("\n=== 测试3：市场冲击估算 ===")
    impact = splitter.estimate_impact(
        total_quantity=0.2,
        current_price=50000,
        market_depth=10.0,  # 订单簿深度10 BTC
        n_splits=5
    )
    
    print(f"不拆分冲击: {impact['impact_no_split_pct']:.4%}")
    print(f"拆分后冲击: {impact['impact_with_split_pct']:.4%}")
    print(f"成本降低: ${impact['cost_reduction']:.2f} ({impact['cost_reduction_pct']:.2f}%)")
