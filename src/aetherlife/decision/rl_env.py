"""
强化学习交易环境
基于 Gymnasium 构建，用于训练 PPO/SAC 算法
"""

import logging
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_AVAILABLE = True
except ImportError:
    _GYM_AVAILABLE = False
    gym = None
    spaces = None

from ..cognition.schemas import Action, Market
from ..memory.store import MemoryStore, TradeEvent

logger = logging.getLogger(__name__)


class TradingEnv(gym.Env):
    """
    强化学习交易环境
    
    状态空间：
    - 市场数据（价格、成交量、订单簿）
    - 持仓信息（当前仓位、未实现盈亏）
    - 历史 PnL
    - 技术指标
    
    动作空间：
    - 连续：[-1, 1] 表示仓位变化（-1=全平空, 0=不变, 1=全开多）
    - 或离散：HOLD/BUY/SELL
    
    奖励函数：
    - Sharpe Ratio
    - PnL
    - 滑点惩罚
    - 回撤惩罚
    - 合规惩罚（如涨跌停交易）
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        initial_balance: float = 10000,
        max_position: float = 1.0,  # 最大仓位比例
        commission: float = 0.001,  # 手续费 0.1%
        slippage: float = 0.0005,  # 滑点 0.05%
        history_length: int = 100,  # 历史数据长度
        action_type: str = "continuous",  # continuous or discrete
        penalty_violate_limit: float = -10.0,  # 违规惩罚
    ):
        super().__init__()
        
        if not _GYM_AVAILABLE:
            raise ImportError("gymnasium not installed. Run: pip install gymnasium")
        
        self.initial_balance = initial_balance
        self.max_position = max_position
        self.commission = commission
        self.slippage = slippage
        self.history_length = history_length
        self.action_type = action_type
        self.penalty_violate_limit = penalty_violate_limit
        
        # 状态空间维度
        # [价格, 成交量, bid, ask, 持仓, 未实现盈亏, 历史PnL_10, RSI, MACD, ...]
        self.state_dim = 20
        
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.state_dim,),
            dtype=np.float32
        )
        
        # 动作空间
        if action_type == "continuous":
            # 连续动作：[-1, 1] 表示目标仓位
            self.action_space = spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(1,),
                dtype=np.float32
            )
        else:
            # 离散动作：0=HOLD, 1=BUY, 2=SELL
            self.action_space = spaces.Discrete(3)
        
        # 环境状态
        self.balance = initial_balance
        self.position = 0.0  # 当前仓位比例 [-1, 1]
        self.entry_price = 0.0
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        
        # 历史记录
        self.price_history = []
        self.pnl_history = []
        self.action_history = []
        
        # 当前步数
        self.current_step = 0
        self.max_steps = 1000
        
        # 当前价格（由外部 reset 时设置）
        self.current_price = 0.0
        self.current_bid = 0.0
        self.current_ask = 0.0
        self.current_volume = 0.0
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """重置环境"""
        super().reset(seed=seed)
        
        self.balance = self.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        
        self.price_history = []
        self.pnl_history = []
        self.action_history = []
        
        self.current_step = 0
        
        # 从 options 获取初始市场数据
        if options and "price" in options:
            self.current_price = options["price"]
            self.current_bid = options.get("bid", self.current_price * 0.999)
            self.current_ask = options.get("ask", self.current_price * 1.001)
            self.current_volume = options.get("volume", 0.0)
        else:
            # 默认值
            self.current_price = 100.0
            self.current_bid = 99.9
            self.current_ask = 100.1
            self.current_volume = 1000.0
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, info
    
    def step(
        self,
        action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        执行一步
        
        Returns:
            observation, reward, terminated, truncated, info
        """
        self.current_step += 1
        
        # 解析动作
        if self.action_type == "continuous":
            target_position = float(np.clip(action[0], -self.max_position, self.max_position))
        else:
            # 离散动作：0=HOLD, 1=BUY(+0.1), 2=SELL(-0.1)
            if action == 0:
                target_position = self.position
            elif action == 1:
                target_position = min(self.position + 0.1, self.max_position)
            else:
                target_position = max(self.position - 0.1, -self.max_position)
        
        # 计算仓位变化
        position_change = target_position - self.position
        
        # 执行交易
        trade_price, trade_cost = self._execute_trade(position_change)
        
        # 更新未实现盈亏
        if self.position != 0:
            self.unrealized_pnl = self.position * self.balance * (self.current_price - self.entry_price) / self.entry_price
        else:
            self.unrealized_pnl = 0.0
        
        # 计算奖励
        reward = self._calculate_reward(position_change, trade_cost)
        
        # 记录历史
        self.price_history.append(self.current_price)
        self.pnl_history.append(self.realized_pnl + self.unrealized_pnl)
        self.action_history.append(target_position)
        
        # 保留最近 N 个数据点
        if len(self.price_history) > self.history_length:
            self.price_history.pop(0)
            self.pnl_history.pop(0)
            self.action_history.pop(0)
        
        # 检查终止条件
        terminated = False
        truncated = False
        
        # 破产
        if self.balance + self.unrealized_pnl <= 0:
            terminated = True
            reward -= 100  # 严重惩罚
        
        # 达到最大步数
        if self.current_step >= self.max_steps:
            truncated = True
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, reward, terminated, truncated, info
    
    def _execute_trade(self, position_change: float) -> Tuple[float, float]:
        """
        执行交易
        
        Returns:
            trade_price: 成交价格
            trade_cost: 交易成本（手续费+滑点）
        """
        if abs(position_change) < 1e-6:
            return self.current_price, 0.0
        
        # 确定交易价格（买入用 ask，卖出用 bid）
        if position_change > 0:
            # 买入
            trade_price = self.current_ask * (1 + self.slippage)
        else:
            # 卖出
            trade_price = self.current_bid * (1 - self.slippage)
        
        # 计算交易金额
        trade_amount = abs(position_change) * self.balance
        
        # 手续费
        commission_cost = trade_amount * self.commission
        
        # 更新持仓
        old_position = self.position
        self.position += position_change
        
        # 更新入场价（加权平均）
        if self.position != 0:
            if old_position * self.position > 0:
                # 同向加仓
                total_value = old_position * self.balance * self.entry_price + position_change * self.balance * trade_price
                self.entry_price = total_value / (self.position * self.balance)
            else:
                # 反向或新开仓
                self.entry_price = trade_price
        else:
            # 平仓
            realized_change = old_position * self.balance * (trade_price - self.entry_price) / self.entry_price
            self.realized_pnl += realized_change
            self.entry_price = 0.0
        
        # 扣除手续费
        self.balance -= commission_cost
        
        total_cost = commission_cost + abs(position_change) * self.balance * self.slippage
        
        return trade_price, total_cost
    
    def _calculate_reward(self, position_change: float, trade_cost: float) -> float:
        """
        计算奖励
        
        奖励函数：
        1. 基础：PnL 变化
        2. 惩罚：交易成本
        3. 惩罚：回撤
        4. 奖励：Sharpe Ratio
        """
        # 1. PnL 变化
        total_pnl = self.realized_pnl + self.unrealized_pnl
        pnl_pct = total_pnl / self.initial_balance
        
        reward = pnl_pct * 100  # 放大到合理范围
        
        # 2. 交易成本惩罚
        cost_penalty = -(trade_cost / self.balance) * 50
        reward += cost_penalty
        
        # 3. 回撤惩罚
        if len(self.pnl_history) > 0:
            max_pnl = max(self.pnl_history)
            current_pnl = self.pnl_history[-1]
            drawdown = (max_pnl - current_pnl) / self.initial_balance if max_pnl > 0 else 0
            
            if drawdown > 0.05:  # 回撤超过5%
                reward -= drawdown * 100
        
        # 4. Sharpe Ratio 奖励（需要足够历史数据）
        if len(self.pnl_history) >= 30:
            returns = np.diff(self.pnl_history[-30:])
            if len(returns) > 0 and np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
                reward += sharpe * 2
        
        return float(reward)
    
    def _get_observation(self) -> np.ndarray:
        """
        构建观察向量
        
        维度说明：
        0: 当前价格（归一化）
        1: 成交量（归一化）
        2: Bid-Ask Spread
        3: 持仓比例
        4: 未实现盈亏比例
        5-14: 最近10步的价格变化率
        15: 当前 Sharpe Ratio
        16-19: 技术指标（RSI、MACD等）
        """
        obs = np.zeros(self.state_dim, dtype=np.float32)
        
        # 价格（归一化到 [-1, 1]）
        if len(self.price_history) > 0:
            price_mean = np.mean(self.price_history[-50:]) if len(self.price_history) >= 50 else self.current_price
            price_std = np.std(self.price_history[-50:]) if len(self.price_history) >= 50 else 1.0
            obs[0] = (self.current_price - price_mean) / (price_std + 1e-8)
        else:
            obs[0] = 0.0
        
        # 成交量
        obs[1] = np.log(self.current_volume + 1) / 10
        
        # Bid-Ask Spread
        spread = (self.current_ask - self.current_bid) / self.current_price if self.current_price > 0 else 0
        obs[2] = spread * 10000  # bps
        
        # 持仓
        obs[3] = self.position
        
        # 未实现盈亏比例
        obs[4] = self.unrealized_pnl / self.initial_balance if self.initial_balance > 0 else 0
        
        # 最近10步价格变化率
        if len(self.price_history) >= 2:
            returns = np.diff(self.price_history[-11:]) / (np.array(self.price_history[-11:-1]) + 1e-8)
            for i, ret in enumerate(returns[-10:]):
                obs[5 + i] = ret * 100  # 百分比
        
        # Sharpe Ratio
        if len(self.pnl_history) >= 30:
            returns = np.diff(self.pnl_history[-30:])
            if np.std(returns) > 0:
                obs[15] = (np.mean(returns) / np.std(returns) * np.sqrt(252)) / 5  # 归一化
        
        # 技术指标（简化，实际应该计算真实指标）
        if len(self.price_history) >= 14:
            # RSI
            prices = np.array(self.price_history[-14:])
            deltas = np.diff(prices)
            gains = deltas[deltas > 0].sum()
            losses = -deltas[deltas < 0].sum()
            rs = gains / (losses + 1e-8)
            rsi = 100 - (100 / (1 + rs))
            obs[16] = (rsi - 50) / 50  # 归一化到 [-1, 1]
        
        return obs
    
    def _get_info(self) -> Dict[str, Any]:
        """返回额外信息"""
        return {
            "balance": self.balance,
            "position": self.position,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.realized_pnl + self.unrealized_pnl,
            "pnl_pct": (self.realized_pnl + self.unrealized_pnl) / self.initial_balance,
            "current_step": self.current_step,
            "sharpe": self._calculate_sharpe(),
        }
    
    def _calculate_sharpe(self) -> float:
        """计算 Sharpe Ratio"""
        if len(self.pnl_history) < 30:
            return 0.0
        
        returns = np.diff(self.pnl_history[-30:])
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))
    
    def render(self):
        """可视化（可选）"""
        print(f"Step: {self.current_step}")
        print(f"Price: {self.current_price:.2f}")
        print(f"Position: {self.position:.2%}")
        print(f"PnL: {self.realized_pnl + self.unrealized_pnl:.2f} ({(self.realized_pnl + self.unrealized_pnl)/self.initial_balance:.2%})")
        print(f"Sharpe: {self._calculate_sharpe():.2f}")
        print("-" * 40)
    
    def update_market_data(self, price: float, bid: float, ask: float, volume: float):
        """
        更新市场数据（用于实时环境）
        
        Args:
            price: 最新价格
            bid: 买一价
            ask: 卖一价
            volume: 成交量
        """
        self.current_price = price
        self.current_bid = bid
        self.current_ask = ask
        self.current_volume = volume
