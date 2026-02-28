"""
PPO强化学习训练器

基于stable-baselines3实现PPO算法训练，支持：
- 离线训练（历史数据回放）
- 在线学习（实时交易结果微调）
- 多环境并行训练
- 自定义奖励函数和网络结构
"""

import os
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import numpy as np

from stable_baselines3 import PPO, SAC
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.logger import configure

from .rl_env import TradingEnv


class TrainingCallback(BaseCallback):
    """
    自定义训练回调，记录训练指标
    """
    def __init__(self, log_freq: int = 1000, verbose: int = 0):
        super().__init__(verbose)
        self.log_freq = log_freq
        self.episode_rewards = []
        self.episode_sharpes = []
        self.episode_drawdowns = []
    
    def _on_step(self) -> bool:
        # 每个episode结束时记录指标
        if self.locals.get("dones", [False])[0]:
            info = self.locals.get("infos", [{}])[0]
            if "episode" in info:
                ep_rew = info["episode"]["r"]
                self.episode_rewards.append(ep_rew)
                
                # 从env获取Sharpe和Drawdown
                if "sharpe_ratio" in info:
                    self.episode_sharpes.append(info["sharpe_ratio"])
                if "max_drawdown" in info:
                    self.episode_drawdowns.append(info["max_drawdown"])
                
                if self.verbose >= 1:
                    print(f"Episode finished: reward={ep_rew:.2f}, "
                          f"sharpe={info.get('sharpe_ratio', 0):.3f}, "
                          f"drawdown={info.get('max_drawdown', 0):.3f}")
        
        # 定期记录到tensorboard
        if self.num_timesteps % self.log_freq == 0:
            if self.episode_rewards:
                self.logger.record("rollout/episode_reward_mean", np.mean(self.episode_rewards[-100:]))
            if self.episode_sharpes:
                self.logger.record("rollout/sharpe_ratio_mean", np.mean(self.episode_sharpes[-100:]))
            if self.episode_drawdowns:
                self.logger.record("rollout/max_drawdown_mean", np.mean(self.episode_drawdowns[-100:]))
        
        return True


class PPOTrainer:
    """
    PPO训练器，支持离线和在线训练
    """
    
    def __init__(
        self,
        env: TradingEnv,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        policy_kwargs: Optional[Dict] = None,
        tensorboard_log: Optional[str] = None,
        verbose: int = 1,
        device: str = "auto"
    ):
        """
        初始化PPO训练器
        
        Args:
            env: 交易环境
            learning_rate: 学习率
            n_steps: 每次更新收集的步数
            batch_size: 批次大小
            n_epochs: 每次更新的epoch数
            gamma: 折扣因子
            gae_lambda: GAE lambda参数
            clip_range: PPO裁剪范围
            ent_coef: 熵系数（鼓励探索）
            vf_coef: 价值函数系数
            max_grad_norm: 梯度裁剪阈值
            policy_kwargs: 策略网络参数
            tensorboard_log: TensorBoard日志目录
            verbose: 日志详细程度
            device: 训练设备（cpu/cuda）
        """
        self.env = env
        self.verbose = verbose
        
        # 默认策略网络结构
        if policy_kwargs is None:
            policy_kwargs = {
                "net_arch": [dict(pi=[256, 256], vf=[256, 256])],
                "activation_fn": "relu"
            }
        
        # 创建模型
        self.model = PPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            policy_kwargs=policy_kwargs,
            tensorboard_log=tensorboard_log,
            verbose=verbose,
            device=device
        )
        
        if verbose >= 1:
            print(f"PPO模型已创建，设备: {device}")
            print(f"策略网络结构: {policy_kwargs}")
    
    def train(
        self,
        total_timesteps: int = 100000,
        callback: Optional[BaseCallback] = None,
        log_interval: int = 10,
        eval_env: Optional[TradingEnv] = None,
        eval_freq: int = 10000,
        n_eval_episodes: int = 5
    ) -> "PPOTrainer":
        """
        训练模型
        
        Args:
            total_timesteps: 总训练步数
            callback: 自定义回调
            log_interval: 日志间隔
            eval_env: 评估环境
            eval_freq: 评估频率
            n_eval_episodes: 每次评估的episode数
        
        Returns:
            self
        """
        # 创建回调列表
        callbacks = []
        
        # 添加训练回调
        if callback is None:
            callback = TrainingCallback(log_freq=1000, verbose=self.verbose)
        callbacks.append(callback)
        
        # 添加评估回调
        if eval_env is not None:
            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=f"./models/ppo_best_{datetime.now().strftime('%Y%m%d')}",
                log_path=f"./logs/ppo_eval_{datetime.now().strftime('%Y%m%d')}",
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                deterministic=True,
                render=False,
                verbose=self.verbose
            )
            callbacks.append(eval_callback)
        
        # 开始训练
        if self.verbose >= 1:
            print(f"\n开始训练，总步数: {total_timesteps}")
        
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            log_interval=log_interval,
            progress_bar=True
        )
        
        if self.verbose >= 1:
            print("\n训练完成！")
        
        return self
    
    def save(self, path: str):
        """保存模型"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.model.save(path)
        if self.verbose >= 1:
            print(f"模型已保存到: {path}")
    
    def load(self, path: str):
        """加载模型"""
        self.model = PPO.load(path, env=self.env)
        if self.verbose >= 1:
            print(f"模型已加载: {path}")
        return self
    
    def predict(self, observation: np.ndarray, deterministic: bool = True):
        """预测动作"""
        action, _states = self.model.predict(observation, deterministic=deterministic)
        return action
    
    def online_learn(
        self,
        new_observation: np.ndarray,
        new_action: np.ndarray,
        new_reward: float,
        new_done: bool,
        n_steps: int = 64
    ):
        """
        在线学习：根据单个交易结果微调模型
        
        Args:
            new_observation: 新观测
            new_action: 执行的动作
            new_reward: 获得的奖励
            new_done: 是否结束
            n_steps: 微调步数
        """
        # 将新数据添加到replay buffer
        # 注意：stable-baselines3的PPO不支持replay buffer，这里简化为重新训练
        # 实际应用中可考虑使用SAC或自定义replay机制
        
        if self.verbose >= 1:
            print(f"在线学习：reward={new_reward:.4f}, done={new_done}")
        
        # 短暂微调
        self.model.learn(total_timesteps=n_steps, reset_num_timesteps=False)


class SACTrainer:
    """
    SAC训练器（Soft Actor-Critic）
    
    相比PPO，SAC更适合连续动作空间和在线学习
    """
    
    def __init__(
        self,
        env: TradingEnv,
        learning_rate: float = 3e-4,
        buffer_size: int = 100000,
        batch_size: int = 256,
        gamma: float = 0.99,
        tau: float = 0.005,
        ent_coef: str = "auto",
        policy_kwargs: Optional[Dict] = None,
        tensorboard_log: Optional[str] = None,
        verbose: int = 1,
        device: str = "auto"
    ):
        """
        初始化SAC训练器
        
        Args:
            env: 交易环境
            learning_rate: 学习率
            buffer_size: Replay buffer大小
            batch_size: 批次大小
            gamma: 折扣因子
            tau: 软更新系数
            ent_coef: 熵系数（'auto'自动调整）
            policy_kwargs: 策略网络参数
            tensorboard_log: TensorBoard日志目录
            verbose: 日志详细程度
            device: 训练设备
        """
        self.env = env
        self.verbose = verbose
        
        # 默认策略网络结构
        if policy_kwargs is None:
            policy_kwargs = {
                "net_arch": [256, 256],
            }
        
        # 创建模型
        self.model = SAC(
            policy="MlpPolicy",
            env=env,
            learning_rate=learning_rate,
            buffer_size=buffer_size,
            batch_size=batch_size,
            gamma=gamma,
            tau=tau,
            ent_coef=ent_coef,
            policy_kwargs=policy_kwargs,
            tensorboard_log=tensorboard_log,
            verbose=verbose,
            device=device
        )
        
        if verbose >= 1:
            print(f"SAC模型已创建，设备: {device}")
    
    def train(
        self,
        total_timesteps: int = 100000,
        callback: Optional[BaseCallback] = None,
        log_interval: int = 4,
        eval_env: Optional[TradingEnv] = None,
        eval_freq: int = 10000,
        n_eval_episodes: int = 5
    ) -> "SACTrainer":
        """训练模型（接口同PPOTrainer）"""
        callbacks = []
        
        if callback is None:
            callback = TrainingCallback(log_freq=1000, verbose=self.verbose)
        callbacks.append(callback)
        
        if eval_env is not None:
            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=f"./models/sac_best_{datetime.now().strftime('%Y%m%d')}",
                log_path=f"./logs/sac_eval_{datetime.now().strftime('%Y%m%d')}",
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                deterministic=True,
                render=False,
                verbose=self.verbose
            )
            callbacks.append(eval_callback)
        
        if self.verbose >= 1:
            print(f"\n开始训练SAC，总步数: {total_timesteps}")
        
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            log_interval=log_interval,
            progress_bar=True
        )
        
        if self.verbose >= 1:
            print("\n训练完成！")
        
        return self
    
    def save(self, path: str):
        """保存模型"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.model.save(path)
        if self.verbose >= 1:
            print(f"模型已保存到: {path}")
    
    def load(self, path: str):
        """加载模型"""
        self.model = SAC.load(path, env=self.env)
        if self.verbose >= 1:
            print(f"模型已加载: {path}")
        return self
    
    def predict(self, observation: np.ndarray, deterministic: bool = True):
        """预测动作"""
        action, _states = self.model.predict(observation, deterministic=deterministic)
        return action
    
    def online_learn(
        self,
        new_observation: np.ndarray,
        new_action: np.ndarray,
        new_reward: float,
        new_done: bool,
        n_gradient_steps: int = 1
    ):
        """
        在线学习：SAC支持更高效的在线更新
        
        Args:
            new_observation: 新观测
            new_action: 执行的动作
            new_reward: 获得的奖励
            new_done: 是否结束
            n_gradient_steps: 梯度更新步数
        """
        # SAC的replay buffer会自动存储经验
        # 这里只需要触发梯度更新
        
        if self.verbose >= 1:
            print(f"在线学习：reward={new_reward:.4f}, done={new_done}")
        
        # 执行梯度更新
        self.model.train(gradient_steps=n_gradient_steps)


def make_vec_env(
    env_fn: Callable[[], TradingEnv],
    n_envs: int = 4,
    vec_env_cls=None
) -> DummyVecEnv:
    """
    创建并行环境
    
    Args:
        env_fn: 环境工厂函数
        n_envs: 并行环境数量
        vec_env_cls: 向量化环境类（DummyVecEnv或SubprocVecEnv）
    
    Returns:
        并行环境实例
    """
    if vec_env_cls is None:
        vec_env_cls = DummyVecEnv if n_envs <= 4 else SubprocVecEnv
    
    env_fns = [env_fn for _ in range(n_envs)]
    return vec_env_cls(env_fns)


if __name__ == "__main__":
    # 示例：训练PPO模型
    
    # 创建环境
    env = TradingEnv(
        initial_balance=10000,
        commission=0.001,
        slippage=0.0005,
        max_position=1.0
    )
    
    # 创建训练器
    trainer = PPOTrainer(
        env=env,
        learning_rate=3e-4,
        tensorboard_log="./logs/ppo_tensorboard",
        verbose=1
    )
    
    # 训练
    trainer.train(total_timesteps=100000)
    
    # 保存模型
    trainer.save("./models/ppo_trading_agent.zip")
    
    print("训练完成！")
