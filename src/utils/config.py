"""
配置校验与默认值
"""

import os
from typing import Any, Dict, List

# 支持的交易所
SUPPORTED_EXCHANGES = ("binance", "okx")

# 支持的策略
SUPPORTED_STRATEGIES = ("breakout", "grid", "ma_cross", "rsi", "volume")


def validate_config(config: Dict[str, Any]) -> List[str]:
    """校验配置，返回错误信息列表，空表示通过。"""
    errors: List[str] = []
    ex = (config.get("exchange") or "binance").lower()
    if ex not in SUPPORTED_EXCHANGES:
        errors.append(f"不支持的交易所: {ex}，可选: {SUPPORTED_EXCHANGES}")
    symbols = config.get("symbols")
    if not symbols or not isinstance(symbols, list):
        errors.append("配置项 symbols 须为非空列表")
    elif not all(isinstance(s, str) and s for s in symbols):
        errors.append("symbols 中每项须为非空字符串")
    strategy = (config.get("strategy") or "breakout").lower()
    if strategy not in SUPPORTED_STRATEGIES:
        errors.append(f"不支持的策略: {strategy}，可选: {SUPPORTED_STRATEGIES}")
    risk = config.get("risk")
    if risk is not None and isinstance(risk, dict):
        if risk.get("max_position_pct") is not None:
            pct = risk["max_position_pct"]
            if not (0 < pct <= 1):
                errors.append("risk.max_position_pct 须在 (0, 1] 之间")
        if risk.get("stop_loss_pct") is not None and risk["stop_loss_pct"] <= 0:
            errors.append("risk.stop_loss_pct 须大于 0")
    return errors


def deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并 override 到 base，不修改原字典。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
