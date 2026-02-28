"""
决策层（Decision Layer）

基于强化学习（PPO/SAC）的交易决策，包含：
- 强化学习环境（Gymnasium）
- PPO/SAC训练器
- 奖励函数塑形
- 模型管理器
"""

from .rl_env import TradingEnv
from .ppo_agent import PPOTrainer, SACTrainer, make_vec_env
from .reward_shaping import RewardShaper, StockConnectSlippagePredictor, ComplianceChecker
from .model_manager import ModelManager, ModelMetadata

__all__ = [
    "TradingEnv",
    "PPOTrainer",
    "SACTrainer",
    "make_vec_env",
    "RewardShaper",
    "StockConnectSlippagePredictor",
    "ComplianceChecker",
    "ModelManager",
    "ModelMetadata"
]
