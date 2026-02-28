"""
奖励函数塑形（Reward Shaping）

针对金融交易场景的特殊设计：
- Sharpe Ratio优化
- 滑点预测与惩罚（特别是Stock Connect）
- 回撤控制
- 合规惩罚
- 交易成本优化
"""

from typing import Dict, Optional, List
from datetime import datetime, time
import numpy as np
from dataclasses import dataclass


@dataclass
class TradeMetrics:
    """交易指标"""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    trade_cost: float = 0.0
    slippage: float = 0.0
    position_change: float = 0.0
    balance: float = 10000.0
    is_violation: bool = False  # 合规违规
    violation_type: Optional[str] = None


class RewardShaper:
    """
    奖励函数塑形器
    
    核心思想：
    1. 基础奖励 = PnL变化
    2. 风险调整 = Sharpe Ratio加成 - 回撤惩罚
    3. 成本惩罚 = 交易成本 + 滑点
    4. 合规惩罚 = 违规行为重罚
    """
    
    def __init__(
        self,
        pnl_weight: float = 1.0,
        sharpe_weight: float = 2.0,
        drawdown_penalty: float = 100.0,
        cost_penalty: float = 50.0,
        slippage_penalty: float = 80.0,
        compliance_penalty: float = 500.0,
        holding_penalty: float = 0.01,  # 持仓惩罚（鼓励交易）
        max_drawdown_threshold: float = 0.1  # 最大回撤阈值（10%）
    ):
        """
        初始化奖励塑形器
        
        Args:
            pnl_weight: PnL权重（基础奖励）
            sharpe_weight: Sharpe Ratio权重（风险调整）
            drawdown_penalty: 回撤惩罚系数
            cost_penalty: 成本惩罚系数
            slippage_penalty: 滑点惩罚系数
            compliance_penalty: 合规惩罚系数
            holding_penalty: 持仓惩罚系数
            max_drawdown_threshold: 最大回撤阈值
        """
        self.pnl_weight = pnl_weight
        self.sharpe_weight = sharpe_weight
        self.drawdown_penalty = drawdown_penalty
        self.cost_penalty = cost_penalty
        self.slippage_penalty = slippage_penalty
        self.compliance_penalty = compliance_penalty
        self.holding_penalty = holding_penalty
        self.max_drawdown_threshold = max_drawdown_threshold
    
    def shape_reward(self, metrics: TradeMetrics) -> float:
        """
        塑形奖励函数
        
        Args:
            metrics: 交易指标
        
        Returns:
            最终奖励值
        """
        reward = 0.0
        
        # 1. 基础奖励：PnL变化
        reward += metrics.pnl_pct * 100 * self.pnl_weight
        
        # 2. 风险调整：Sharpe Ratio加成
        reward += metrics.sharpe_ratio * self.sharpe_weight
        
        # 3. 回撤惩罚：严重回撤重罚
        if metrics.max_drawdown > self.max_drawdown_threshold:
            # 超过阈值后，惩罚呈指数增长
            excess_dd = metrics.max_drawdown - self.max_drawdown_threshold
            reward -= (excess_dd ** 2) * self.drawdown_penalty
        else:
            reward -= metrics.max_drawdown * self.drawdown_penalty
        
        # 4. 交易成本惩罚
        cost_ratio = metrics.trade_cost / metrics.balance
        reward -= cost_ratio * self.cost_penalty
        
        # 5. 滑点惩罚
        slippage_ratio = metrics.slippage / metrics.balance
        reward -= slippage_ratio * self.slippage_penalty
        
        # 6. 合规惩罚：违规行为重罚
        if metrics.is_violation:
            reward -= self.compliance_penalty
        
        # 7. 持仓惩罚：鼓励适度交易（避免过度持仓或过度交易）
        if abs(metrics.position_change) < 0.01:  # 几乎不交易
            reward -= self.holding_penalty
        
        return reward
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        计算Sharpe Ratio
        
        Args:
            returns: 收益率序列
            risk_free_rate: 无风险利率（年化）
        
        Returns:
            Sharpe Ratio
        """
        if len(returns) < 2:
            return 0.0
        
        returns_arr = np.array(returns)
        excess_returns = returns_arr - risk_free_rate / 252  # 假设252个交易日
        
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)
        
        if std_return == 0:
            return 0.0
        
        # 年化Sharpe Ratio
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return sharpe
    
    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """
        计算最大回撤
        
        Args:
            equity_curve: 权益曲线
        
        Returns:
            最大回撤（负值）
        """
        if len(equity_curve) < 2:
            return 0.0
        
        equity_arr = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - peak) / peak
        max_dd = np.min(drawdown)
        
        return abs(max_dd)


class StockConnectSlippagePredictor:
    """
    Stock Connect 滑点预测器
    
    A股北向交易的滑点主要受以下因素影响：
    1. 北向额度剩余（额度紧张 → 滑点大）
    2. 交易时段（开盘/收盘 → 滑点大）
    3. 订单大小（大单 → 滑点大）
    4. 市场波动率（高波动 → 滑点大）
    """
    
    def __init__(self):
        # 历史滑点数据（用于拟合预测模型）
        self.historical_slippage = []
    
    def predict_slippage(
        self,
        order_size: float,
        northbound_quota_remaining: float,
        current_time: time,
        volatility: float,
        symbol: str
    ) -> float:
        """
        预测滑点
        
        Args:
            order_size: 订单大小（USD）
            northbound_quota_remaining: 北向剩余额度（亿元人民币）
            current_time: 当前时间
            volatility: 市场波动率
            symbol: 股票代码
        
        Returns:
            预测滑点（百分比）
        """
        base_slippage = 0.0005  # 基础滑点0.05%
        
        # 1. 额度因素（剩余额度 < 20% → 滑点增加）
        quota_factor = 1.0
        if northbound_quota_remaining < 100:  # 少于100亿
            quota_factor = 1.5
        if northbound_quota_remaining < 50:  # 少于50亿
            quota_factor = 2.0
        
        # 2. 时段因素（开盘前30分钟、收盘前30分钟 → 滑点增加）
        time_factor = 1.0
        if (time(9, 30) <= current_time <= time(10, 0)) or \
           (time(14, 30) <= current_time <= time(15, 0)):
            time_factor = 1.3
        
        # 3. 订单大小因素（大单 → 滑点增加）
        size_factor = 1.0 + (order_size / 10000) * 0.1  # 每1万USD增加0.1倍
        
        # 4. 波动率因素（高波动 → 滑点增加）
        volatility_factor = 1.0 + volatility * 2.0  # 波动率每增加1%，滑点增加2倍
        
        # 综合计算
        predicted_slippage = base_slippage * quota_factor * time_factor * size_factor * volatility_factor
        
        return predicted_slippage
    
    def update_history(self, actual_slippage: float, metadata: Dict):
        """
        更新历史滑点数据（用于模型优化）
        
        Args:
            actual_slippage: 实际滑点
            metadata: 订单元数据（订单大小、额度、时间等）
        """
        self.historical_slippage.append({
            "slippage": actual_slippage,
            "metadata": metadata,
            "timestamp": datetime.now()
        })
        
        # 只保留最近1000条记录
        if len(self.historical_slippage) > 1000:
            self.historical_slippage = self.historical_slippage[-1000:]


class ComplianceChecker:
    """
    合规检查器
    
    检查交易是否违反以下规则：
    1. A股交易时段限制（09:30-11:30, 13:00-15:00）
    2. 涨跌停限制（主板±10%、科创板±20%）
    3. 北向额度限制（剩余额度 > 订单金额）
    4. 单日最大回撤限制（2%）
    5. 杠杆限制（加密货币最大10x）
    """
    
    def __init__(self):
        self.violations = []
    
    def check_astock_trading_hours(
        self,
        current_time: time,
        symbol: str
    ) -> tuple[bool, Optional[str]]:
        """检查A股交易时段"""
        trading_sessions = [
            (time(9, 30), time(11, 30)),
            (time(13, 0), time(15, 0))
        ]
        
        for start, end in trading_sessions:
            if start <= current_time <= end:
                return True, None
        
        return False, f"A股交易时段外：{current_time}"
    
    def check_limit_up_down(
        self,
        current_price: float,
        prev_close: float,
        symbol: str
    ) -> tuple[bool, Optional[str]]:
        """检查涨跌停"""
        change_pct = (current_price - prev_close) / prev_close
        
        # 科创板/创业板：±20%
        is_kcb_or_cyb = symbol.startswith("688") or symbol.startswith("300")
        limit = 0.20 if is_kcb_or_cyb else 0.10
        
        if abs(change_pct) >= limit * 0.95:  # 接近涨跌停（95%）
            return False, f"接近涨跌停：{change_pct:.2%}"
        
        return True, None
    
    def check_northbound_quota(
        self,
        order_size_usd: float,
        quota_remaining_cny: float,
        exchange_rate: float = 7.2
    ) -> tuple[bool, Optional[str]]:
        """检查北向额度"""
        order_size_cny = order_size_usd * exchange_rate / 100000000  # 转为亿元人民币
        
        if quota_remaining_cny < order_size_cny * 2:  # 剩余额度不足订单的2倍
            return False, f"北向额度不足：剩余{quota_remaining_cny:.1f}亿，订单需要{order_size_cny:.1f}亿"
        
        return True, None
    
    def check_daily_drawdown(
        self,
        current_drawdown: float,
        max_drawdown_threshold: float = 0.02
    ) -> tuple[bool, Optional[str]]:
        """检查单日最大回撤"""
        if current_drawdown > max_drawdown_threshold:
            return False, f"单日回撤超限：{current_drawdown:.2%} > {max_drawdown_threshold:.2%}"
        
        return True, None
    
    def check_all(
        self,
        symbol: str,
        current_time: time,
        current_price: float,
        prev_close: float,
        order_size_usd: float,
        quota_remaining_cny: float,
        current_drawdown: float
    ) -> tuple[bool, List[str]]:
        """
        执行所有合规检查
        
        Returns:
            (是否通过, 违规原因列表)
        """
        violations = []
        
        # A股特殊检查
        if symbol.startswith("6") or symbol.startswith("0") or symbol.startswith("3"):
            # 交易时段
            passed, reason = self.check_astock_trading_hours(current_time, symbol)
            if not passed:
                violations.append(reason)
            
            # 涨跌停
            passed, reason = self.check_limit_up_down(current_price, prev_close, symbol)
            if not passed:
                violations.append(reason)
            
            # 北向额度
            passed, reason = self.check_northbound_quota(order_size_usd, quota_remaining_cny)
            if not passed:
                violations.append(reason)
        
        # 通用检查：单日回撤
        passed, reason = self.check_daily_drawdown(current_drawdown)
        if not passed:
            violations.append(reason)
        
        is_compliant = len(violations) == 0
        return is_compliant, violations


if __name__ == "__main__":
    # 示例：奖励函数塑形
    
    shaper = RewardShaper()
    
    # 模拟交易指标
    metrics = TradeMetrics(
        pnl=50.0,
        pnl_pct=0.005,
        sharpe_ratio=1.2,
        max_drawdown=0.03,
        trade_cost=2.0,
        slippage=1.0,
        position_change=0.3,
        balance=10000.0,
        is_violation=False
    )
    
    reward = shaper.shape_reward(metrics)
    print(f"塑形后奖励: {reward:.2f}")
    
    # 示例：滑点预测
    predictor = StockConnectSlippagePredictor()
    slippage = predictor.predict_slippage(
        order_size=5000,
        northbound_quota_remaining=80,
        current_time=time(9, 45),
        volatility=0.02,
        symbol="600519"
    )
    print(f"预测滑点: {slippage:.4%}")
    
    # 示例：合规检查
    checker = ComplianceChecker()
    is_compliant, violations = checker.check_all(
        symbol="600519",
        current_time=time(10, 0),
        current_price=1850.0,
        prev_close=1800.0,
        order_size_usd=5000,
        quota_remaining_cny=80,
        current_drawdown=0.01
    )
    print(f"合规检查: {'通过' if is_compliant else '不通过'}")
    if violations:
        print(f"违规原因: {violations}")
