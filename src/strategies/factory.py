"""策略工厂：根据类型名和配置创建策略实例。"""

from .base import BaseStrategy
from .breakout import BreakoutStrategy
from .grid import GridStrategy
from .macd import MACrossStrategy
from .rsi import RSIStrategy
from .volume import VolumeStrategy
from .multi import MultiStrategy


def create_strategy(strategy_type: str, config: dict) -> BaseStrategy:
    """
    根据策略类型和配置创建策略实例。

    :param strategy_type: 策略类型，支持 "breakout"、"grid"、"ma_cross"、"rsi"、"volume"、"multi"
    :param config: 策略参数字典，具体字段由各策略定义；multi 需 "strategies" 与可选 "weights"
    :return: 策略实例，可用于 generate_signals(df) 等
    :raises ValueError: 未知的 strategy_type 时抛出
    """
    strategies = {
        "breakout": BreakoutStrategy,
        "grid": GridStrategy,
        "ma_cross": MACrossStrategy,
        "rsi": RSIStrategy,
        "volume": VolumeStrategy,
        "multi": MultiStrategy
    }
    
    if strategy_type == "multi":
        sub_strategies_config = config.get("strategies", [])
        weights = config.get("weights", [])
        sub_strategies = []
        for s_conf in sub_strategies_config:
            s_type = s_conf.get("type")
            s_cfg = s_conf.get("config", {})
            if s_type:
                sub_strategies.append(create_strategy(s_type, s_cfg))
        return MultiStrategy(sub_strategies, weights if weights else None)

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_type}")
    
    return strategies[strategy_type](config)
