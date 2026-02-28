"""
进化层（Evolution Layer）

策略自我进化功能：
- 回测引擎（可选，需要polars）
- 策略生成器（可选，需要LLM）
- 遗传算法优化器（可选）
"""

# 核心导出（必需）
from .evolution_engine import EvolutionEngine

__all__ = ["EvolutionEngine"]

# 可选模块（仅在依赖满足时导入）
try:
    from .backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
    __all__.extend(["BacktestEngine", "BacktestConfig", "BacktestResult"])
except ImportError as e:
    import warnings
    warnings.warn(f"BacktestEngine 不可用（缺少依赖 polars）: {e}", ImportWarning)

# 预留：策略生成器和遗传算法
try:
    from .strategy_generator import StrategyGenerator
    __all__.append("StrategyGenerator")
except ImportError:
    pass

try:
    from .genetic_optimizer import GeneticOptimizer
    __all__.append("GeneticOptimizer")
except ImportError:
    pass
