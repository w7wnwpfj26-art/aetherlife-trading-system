"""
守护层 (Guard)
风控一票否决、Human-in-the-Loop、杀手开关、审计日志、VaR计算、异常检测、SFC合规
"""

from .risk_guard import RiskGuard, GuardResult
from .advanced_risk import (
    VaRCalculator, 
    VaRResult,
    AnomalyDetector,
    AnomalyAlert,
    HKSFCComplianceChecker,
    ComplianceResult,
    RiskLevel
)

__all__ = [
    "RiskGuard",
    "GuardResult",
    "VaRCalculator",
    "VaRResult",
    "AnomalyDetector",
    "AnomalyAlert",
    "HKSFCComplianceChecker",
    "ComplianceResult",
    "RiskLevel"
]
