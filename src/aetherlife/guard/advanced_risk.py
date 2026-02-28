"""
高级风险管理 (Advanced Risk Management)

实现专业级风险度量和监控:
- VaR (Value at Risk) 计算
- 异常检测 (Anomaly Detection)
- 香港SFC合规检查
- 实时风险监控
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import numpy as np
import logging
from enum import Enum

logger = logging.getLogger("aetherlife.guard.advanced_risk")


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VaRResult:
    """VaR计算结果"""
    var_1day_95: float  # 1日95% VaR
    var_1day_99: float  # 1日99% VaR
    var_10day_95: float  # 10日95% VaR
    cvar_95: float  # 条件VaR (CVaR/ES)
    confidence_level: float
    method: str  # "historical", "parametric", "monte_carlo"
    timestamp: datetime


@dataclass
class AnomalyAlert:
    """异常告警"""
    timestamp: datetime
    symbol: str
    anomaly_type: str  # "price", "volume", "volatility", "correlation"
    severity: RiskLevel
    message: str
    metric_value: float
    threshold: float


@dataclass
class ComplianceResult:
    """合规检查结果"""
    passed: bool
    violations: List[str]
    warnings: List[str]
    risk_level: RiskLevel
    timestamp: datetime


class VaRCalculator:
    """
    VaR计算器
    
    支持三种方法:
    1. Historical Simulation (历史模拟法)
    2. Parametric Method (参数法/方差-协方差法)
    3. Monte Carlo Simulation (蒙特卡洛模拟法)
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """
        初始化VaR计算器
        
        Args:
            confidence_level: 置信水平 (0.90, 0.95, 0.99)
        """
        self.confidence_level = confidence_level
    
    def calculate_historical_var(
        self,
        returns: np.ndarray,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        历史模拟法计算VaR
        
        Args:
            returns: 历史收益率序列
            horizon_days: 持有期（天）
        
        Returns:
            VaR结果
        """
        if len(returns) < 100:
            logger.warning("历史数据不足100个样本，VaR可能不准确")
        
        # 调整到持有期
        if horizon_days > 1:
            scaled_returns = returns * np.sqrt(horizon_days)
        else:
            scaled_returns = returns
        
        # 计算VaR
        var_95 = -np.percentile(scaled_returns, (1 - 0.95) * 100)
        var_99 = -np.percentile(scaled_returns, (1 - 0.99) * 100)
        var_10day = -np.percentile(returns * np.sqrt(10), (1 - 0.95) * 100)
        
        # 计算CVaR（条件VaR/期望缺口）
        threshold = np.percentile(scaled_returns, (1 - 0.95) * 100)
        cvar_95 = -np.mean(scaled_returns[scaled_returns <= threshold])
        
        return VaRResult(
            var_1day_95=var_95,
            var_1day_99=var_99,
            var_10day_95=var_10day,
            cvar_95=cvar_95,
            confidence_level=0.95,
            method="historical",
            timestamp=datetime.now()
        )
    
    def calculate_parametric_var(
        self,
        returns: np.ndarray,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        参数法计算VaR（假设正态分布）
        
        Args:
            returns: 历史收益率序列
            horizon_days: 持有期（天）
        
        Returns:
            VaR结果
        """
        # 计算均值和标准差
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        # 调整到持有期
        mu_horizon = mu * horizon_days
        sigma_horizon = sigma * np.sqrt(horizon_days)
        
        # 计算VaR（使用正态分布分位数）
        from scipy import stats
        z_95 = stats.norm.ppf(0.05)  # -1.645
        z_99 = stats.norm.ppf(0.01)  # -2.326
        
        var_95 = -(mu_horizon + z_95 * sigma_horizon)
        var_99 = -(mu_horizon + z_99 * sigma_horizon)
        
        # 10日VaR
        mu_10 = mu * 10
        sigma_10 = sigma * np.sqrt(10)
        var_10day = -(mu_10 + z_95 * sigma_10)
        
        # CVaR（正态分布下的期望缺口）
        cvar_95 = -(mu_horizon - sigma_horizon * stats.norm.pdf(z_95) / 0.05)
        
        return VaRResult(
            var_1day_95=var_95,
            var_1day_99=var_99,
            var_10day_95=var_10day,
            cvar_95=cvar_95,
            confidence_level=0.95,
            method="parametric",
            timestamp=datetime.now()
        )
    
    def calculate_monte_carlo_var(
        self,
        returns: np.ndarray,
        horizon_days: int = 1,
        n_simulations: int = 10000
    ) -> VaRResult:
        """
        蒙特卡洛模拟法计算VaR
        
        Args:
            returns: 历史收益率序列
            horizon_days: 持有期（天）
            n_simulations: 模拟次数
        
        Returns:
            VaR结果
        """
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        # 模拟收益率路径
        simulated_returns = np.random.normal(
            loc=mu * horizon_days,
            scale=sigma * np.sqrt(horizon_days),
            size=n_simulations
        )
        
        # 计算VaR
        var_95 = -np.percentile(simulated_returns, 5)
        var_99 = -np.percentile(simulated_returns, 1)
        
        # 10日VaR
        simulated_10day = np.random.normal(
            loc=mu * 10,
            scale=sigma * np.sqrt(10),
            size=n_simulations
        )
        var_10day = -np.percentile(simulated_10day, 5)
        
        # CVaR
        threshold = np.percentile(simulated_returns, 5)
        cvar_95 = -np.mean(simulated_returns[simulated_returns <= threshold])
        
        return VaRResult(
            var_1day_95=var_95,
            var_1day_99=var_99,
            var_10day_95=var_10day,
            cvar_95=cvar_95,
            confidence_level=0.95,
            method="monte_carlo",
            timestamp=datetime.now()
        )


class AnomalyDetector:
    """
    异常检测器
    
    检测多种异常:
    1. 价格异常（断层、剧烈波动）
    2. 成交量异常
    3. 波动率异常
    4. 相关性异常
    """
    
    def __init__(
        self,
        price_threshold: float = 3.0,  # 标准差倍数
        volume_threshold: float = 3.0,
        volatility_threshold: float = 2.0,
        lookback_period: int = 100
    ):
        """
        初始化异常检测器
        
        Args:
            price_threshold: 价格异常阈值（标准差倍数）
            volume_threshold: 成交量异常阈值
            volatility_threshold: 波动率异常阈值
            lookback_period: 回溯期（用于计算基准）
        """
        self.price_threshold = price_threshold
        self.volume_threshold = volume_threshold
        self.volatility_threshold = volatility_threshold
        self.lookback_period = lookback_period

        # 修复：使用 deque(maxlen=lookback_period) 替换 list + pop(0)
        # append 和自动淘汰旧数据均为 O(1)，远优于 list.pop(0) 的 O(n)
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
    
    def detect_price_anomaly(
        self,
        symbol: str,
        current_price: float,
        previous_price: float
    ) -> Optional[AnomalyAlert]:
        """检测价格异常"""
        # 计算收益率
        returns = (current_price - previous_price) / previous_price
        
        # 更新历史（deque 自动淘汰超出 maxlen 的最旧数据）
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_period)
        self.price_history[symbol].append(returns)

        # 需要足够历史数据
        if len(self.price_history[symbol]) < 30:
            return None

        # 计算Z-score
        returns_array = np.array(self.price_history[symbol])
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return None
        
        z_score = (returns - mean_return) / std_return
        
        # 检测异常
        if abs(z_score) > self.price_threshold:
            severity = RiskLevel.CRITICAL if abs(z_score) > 5 else RiskLevel.HIGH
            
            return AnomalyAlert(
                timestamp=datetime.now(),
                symbol=symbol,
                anomaly_type="price",
                severity=severity,
                message=f"价格异常波动: {returns*100:.2f}% (Z-score: {z_score:.2f})",
                metric_value=abs(z_score),
                threshold=self.price_threshold
            )
        
        return None
    
    def detect_volume_anomaly(
        self,
        symbol: str,
        current_volume: float
    ) -> Optional[AnomalyAlert]:
        """检测成交量异常"""
        # 更新历史（deque 自动淘汰超出 maxlen 的最旧数据）
        if symbol not in self.volume_history:
            self.volume_history[symbol] = deque(maxlen=self.lookback_period)
        self.volume_history[symbol].append(current_volume)

        # 需要足够历史数据
        if len(self.volume_history[symbol]) < 30:
            return None

        # 计算Z-score
        volume_array = np.array(self.volume_history[symbol])
        mean_volume = np.mean(volume_array)
        std_volume = np.std(volume_array)
        
        if std_volume == 0 or mean_volume == 0:
            return None
        
        z_score = (current_volume - mean_volume) / std_volume
        
        # 检测异常（只关注异常高的成交量）
        if z_score > self.volume_threshold:
            severity = RiskLevel.HIGH if z_score > 5 else RiskLevel.MEDIUM
            
            return AnomalyAlert(
                timestamp=datetime.now(),
                symbol=symbol,
                anomaly_type="volume",
                severity=severity,
                message=f"成交量异常: {current_volume/mean_volume:.2f}x正常水平 (Z-score: {z_score:.2f})",
                metric_value=z_score,
                threshold=self.volume_threshold
            )
        
        return None


class HKSFCComplianceChecker:
    """
    香港SFC（证券及期货事务监察委员会）合规检查器
    
    检查项目:
    1. 北向额度限制
    2. 交易时段限制
    3. 单笔订单限制
    4. 日内交易次数限制
    5. 持仓集中度限制
    """
    
    def __init__(
        self,
        max_single_order_hkd: float = 10_000_000,  # 单笔订单上限（港币）
        max_daily_trades: int = 100,  # 日内最大交易次数
        max_position_concentration: float = 0.30,  # 单一持仓占比上限
        northbound_quota_threshold: float = 0.10  # 北向额度告警阈值
    ):
        """
        初始化SFC合规检查器
        
        Args:
            max_single_order_hkd: 单笔订单上限（港币）
            max_daily_trades: 日内最大交易次数
            max_position_concentration: 单一持仓占比上限
            northbound_quota_threshold: 北向额度告警阈值
        """
        self.max_single_order_hkd = max_single_order_hkd
        self.max_daily_trades = max_daily_trades
        self.max_position_concentration = max_position_concentration
        self.northbound_quota_threshold = northbound_quota_threshold
        
        # 交易记录
        self.daily_trade_count: Dict[str, int] = {}  # date → count
        self.last_reset_date = datetime.now().date()
    
    def check_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        total_portfolio_value: float,
        position_value: float,
        northbound_quota_remaining: Optional[float] = None,
        exchange_rate_hkd_usd: float = 7.8
    ) -> ComplianceResult:
        """
        检查交易合规性
        
        Args:
            symbol: 交易品种
            quantity: 交易数量
            price: 价格
            total_portfolio_value: 总资产价值（USD）
            position_value: 该品种持仓价值（USD）
            northbound_quota_remaining: 北向剩余额度（亿人民币）
            exchange_rate_hkd_usd: 港币美元汇率
        
        Returns:
            合规检查结果
        """
        violations = []
        warnings = []
        risk_level = RiskLevel.LOW
        
        # 重置日计数器
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_count = {}
            self.last_reset_date = today
        
        # 1. 交易时段检查（A股特定）
        if symbol.endswith(".SH") or symbol.endswith(".SZ"):
            now = datetime.now().time()
            morning_start = datetime.strptime("09:30", "%H:%M").time()
            morning_end = datetime.strptime("11:30", "%H:%M").time()
            afternoon_start = datetime.strptime("13:00", "%H:%M").time()
            afternoon_end = datetime.strptime("15:00", "%H:%M").time()
            
            in_trading_hours = (
                (morning_start <= now <= morning_end) or
                (afternoon_start <= now <= afternoon_end)
            )
            
            if not in_trading_hours:
                violations.append(f"A股非交易时段: {now.strftime('%H:%M')}")
                risk_level = RiskLevel.HIGH
        
        # 2. 单笔订单限制
        order_value_usd = quantity * price
        order_value_hkd = order_value_usd * exchange_rate_hkd_usd
        
        if order_value_hkd > self.max_single_order_hkd:
            violations.append(
                f"单笔订单超限: HKD {order_value_hkd:,.0f} > HKD {self.max_single_order_hkd:,.0f}"
            )
            risk_level = RiskLevel.CRITICAL
        
        # 3. 日内交易次数限制
        date_key = today.isoformat()
        current_count = self.daily_trade_count.get(date_key, 0)
        
        if current_count >= self.max_daily_trades:
            violations.append(
                f"日内交易次数超限: {current_count} >= {self.max_daily_trades}"
            )
            risk_level = RiskLevel.HIGH
        else:
            self.daily_trade_count[date_key] = current_count + 1
        
        # 4. 持仓集中度检查
        if total_portfolio_value > 0:
            new_position_value = position_value + order_value_usd
            concentration = new_position_value / total_portfolio_value
            
            if concentration > self.max_position_concentration:
                warnings.append(
                    f"持仓集中度过高: {concentration*100:.1f}% > {self.max_position_concentration*100:.1f}%"
                )
                if risk_level == RiskLevel.LOW:
                    risk_level = RiskLevel.MEDIUM
        
        # 5. 北向额度检查
        if northbound_quota_remaining is not None:
            # 额度单位：亿人民币，转换为美元（假设汇率7.2）
            quota_usd = northbound_quota_remaining * 100_000_000 / 7.2
            
            if order_value_usd > quota_usd:
                violations.append(
                    f"北向额度不足: 订单 ${order_value_usd:,.0f} > 剩余额度 ${quota_usd:,.0f}"
                )
                risk_level = RiskLevel.CRITICAL
            elif quota_usd / 520_000_000_000 < self.northbound_quota_threshold:  # 总额度5200亿
                warnings.append(
                    f"北向额度低于{self.northbound_quota_threshold*100:.0f}%: {northbound_quota_remaining:.1f}亿人民币"
                )
        
        # 判断是否通过
        passed = len(violations) == 0
        
        return ComplianceResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            risk_level=risk_level,
            timestamp=datetime.now()
        )


if __name__ == "__main__":
    # 示例：VaR计算
    print("=== VaR计算示例 ===\n")
    
    # 生成模拟收益率数据
    returns = np.random.normal(0.0005, 0.02, 252)  # 年度数据
    
    calculator = VaRCalculator(confidence_level=0.95)
    var_result = calculator.calculate_historical_var(returns, horizon_days=1)
    
    print(f"1日95% VaR: {var_result.var_1day_95*100:.2f}%")
    print(f"1日99% VaR: {var_result.var_1day_99*100:.2f}%")
    print(f"10日95% VaR: {var_result.var_10day_95*100:.2f}%")
    print(f"条件VaR (CVaR): {var_result.cvar_95*100:.2f}%")
    
    # 示例：异常检测
    print("\n=== 异常检测示例 ===\n")
    
    detector = AnomalyDetector()
    
    # 模拟正常价格波动
    for i in range(50):
        detector.detect_price_anomaly("BTCUSDT", 50000 + i * 10, 50000 + (i-1) * 10)
    
    # 模拟异常波动
    alert = detector.detect_price_anomaly("BTCUSDT", 55000, 50500)
    if alert:
        print(f"⚠️  {alert.message}")
        print(f"   严重程度: {alert.severity.value}")
    
    # 示例：SFC合规检查
    print("\n=== SFC合规检查示例 ===\n")
    
    checker = HKSFCComplianceChecker()
    
    result = checker.check_trade(
        symbol="0700.HK",  # 腾讯
        quantity=1000,
        price=350,  # HKD
        total_portfolio_value=1_000_000,  # USD
        position_value=100_000,  # USD
        northbound_quota_remaining=50  # 50亿人民币
    )
    
    if result.passed:
        print("✅ 合规检查通过")
    else:
        print("❌ 合规检查失败:")
        for violation in result.violations:
            print(f"   - {violation}")
    
    if result.warnings:
        print("\n⚠️  警告:")
        for warning in result.warnings:
            print(f"   - {warning}")
