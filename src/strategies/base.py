
from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Optional


class BaseStrategy(ABC):
    """策略基类"""

    # 合法信号值
    VALID_SIGNAL_VALUES = frozenset({-1, 0, 1})

    def __init__(self, config: dict):
        self.config = config
        self.name = "BaseStrategy"
        self.params = {}

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """分析数据，计算指标"""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        pass

    def validate_signal(self, signal: dict) -> bool:
        """验证信号字典是否有效

        合法信号须满足：
        - 包含 "signal" 键，值为 -1 / 0 / 1
        - 若含 "strength"，须在 [0, 1] 范围内
        - 若含 "price"，须为正数
        """
        if not isinstance(signal, dict):
            return False

        sig_val = signal.get("signal")
        if sig_val not in self.VALID_SIGNAL_VALUES:
            return False

        strength = signal.get("strength")
        if strength is not None and not (0.0 <= float(strength) <= 1.0):
            return False

        price = signal.get("price")
        if price is not None and float(price) <= 0:
            return False

        return True

    def get_params(self) -> dict:
        """获取策略参数"""
        return self.params
