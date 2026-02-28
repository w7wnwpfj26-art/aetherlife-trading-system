"""
AetherLife（以太生命体）— 会交易的数字生命

自主感知、持续学习、自我进化的 AI 交易实体。
分层架构：感知 → 记忆 → 认知(多代理) → 决策 → 执行 → 守护 → 进化。
"""

__version__ = "0.1.0"

from .core.life import AetherLife

__all__ = ["AetherLife", "__version__"]
