"""
风控模块
仓位管理、止损止盈、熔断机制
"""

import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque


class RiskManager:
    """风控管理器"""
    
    def __init__(self, config: dict):
        # 仓位管理
        self.max_position_pct = config.get("max_position_pct", 0.1)  # 最大10%仓位
        self.max_leverage = config.get("max_leverage", 10)
        self.min_position_pct = config.get("min_position_pct", 0.01)  # 最小1%仓位
        
        # 止损止盈
        self.stop_loss_pct = config.get("stop_loss_pct", 0.02)  # 2%止损
        self.take_profit_pct = config.get("take_profit_pct", 0.05)  # 5%止盈
        self.trailing_stop_pct = config.get("trailing_stop_pct", 0.015)  # 追踪止损
        
        # 单日限制
        self.max_daily_loss_pct = config.get("max_daily_loss_pct", 0.1)  # 单日最多亏10%
        self.max_daily_trades = config.get("max_daily_trades", 20)  # 单日最多20笔
        self.max_consecutive_losses = config.get("max_consecutive_losses", 5)  # 最多连亏5次
        
        # 熔断
        self.circuit_breaker_loss_pct = config.get("circuit_breaker_loss_pct", 0.2)  # 亏20%熔断
        self.circuit_breaker_cooldown = config.get("circuit_breaker_cooldown", 3600)  # 冷却1小时
        
        # 状态
        self.daily_stats = {
            "pnl": 0,
            "pnl_pct": 0,
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "start_time": datetime.now()
        }
        
        self.consecutive_losses = 0
        self.last_circuit_breaker_time = 0
        self.is_paused = False
        self.pause_reason = ""
        
        # 交易历史
        self.trade_history = deque(maxlen=1000)

    def _maybe_reset_daily_stats(self):
        """若已进入新的一天则重置日统计"""
        start = self.daily_stats.get("start_time")
        if start is None:
            return
        now = datetime.now()
        if now.date() != start.date():
            self.reset_daily_stats()

    def calculate_position_size(self, signal: dict, balance: float, price: float) -> float:
        """计算仓位大小"""
        if price <= 0 or balance <= 0:
            return 0.0
        base_size = balance * self.max_position_pct
        signal_strength = max(0, min(1, signal.get("strength", 0.5)))
        quantity = (base_size * signal_strength) / price
        min_size = balance * self.min_position_pct / price
        max_size = balance * self.max_position_pct / price
        return max(min_size, min(quantity, max_size))
    
    def check_stop_loss(self, entry_price: float, current_price: float, side: str) -> Dict:
        """检查止损"""
        if entry_price <= 0:
            return {"should_stop": False, "loss_pct": 0, "threshold": self.stop_loss_pct, "reason": None}
        if side.upper() == "LONG":
            loss_pct = (entry_price - current_price) / entry_price
        else:
            loss_pct = (current_price - entry_price) / entry_price
        should_stop = loss_pct >= self.stop_loss_pct
        
        return {
            "should_stop": should_stop,
            "loss_pct": loss_pct,
            "threshold": self.stop_loss_pct,
            "reason": "stop_loss" if should_stop else None
        }
    
    def check_take_profit(self, entry_price: float, current_price: float, side: str) -> Dict:
        """检查止盈"""
        if entry_price <= 0:
            return {"should_stop": False, "profit_pct": 0, "threshold": self.take_profit_pct, "reason": None}
        if side.upper() == "LONG":
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
        should_take = profit_pct >= self.take_profit_pct

        return {
            "should_stop": should_take,   # 修复: 统一使用 should_stop 键与调用方一致
            "profit_pct": profit_pct,
            "threshold": self.take_profit_pct,
            "reason": "take_profit" if should_take else None
        }
    
    def check_trailing_stop(self, entry_price: float, current_price: float, 
                           side: str, peak_price: float) -> Dict:
        """检查追踪止损"""
        if side.upper() == "LONG":
            # 追踪最高点
            current_pnl_pct = (current_price - entry_price) / entry_price
            peak_pnl_pct = (peak_price - entry_price) / entry_price
            
            # 当盈利超过阈值后，开始追踪
            if peak_pnl_pct > self.trailing_stop_pct:
                trailing_stop_price = peak_price * (1 - self.trailing_stop_pct)
                should_stop = current_price <= trailing_stop_price
                
                return {
                    "should_stop": should_stop,
                    "trailing_stop_price": trailing_stop_price,
                    "current_pnl_pct": current_pnl_pct,
                    "reason": "trailing_stop" if should_stop else None
                }
        
        return {"should_stop": False, "reason": None}
    
    def check_circuit_breaker(self) -> Dict:
        """检查熔断"""
        now = time.time()
        
        # 冷却期内不检查
        if now - self.last_circuit_breaker_time < self.circuit_breaker_cooldown:
            return {
                "should_stop": self.is_paused,
                "reason": self.pause_reason,
                "cooldown_remaining": self.circuit_breaker_cooldown - (now - self.last_circuit_breaker_time)
            }
        
        # 检查是否触发熔断
        if self.daily_stats["pnl_pct"] <= -self.circuit_breaker_loss_pct:
            self.is_paused = True
            self.pause_reason = "circuit_breaker"
            self.last_circuit_breaker_time = now
            
            return {
                "should_stop": True,
                "reason": "circuit_breaker",
                "loss_pct": self.daily_stats["pnl_pct"]
            }
        
        return {"should_stop": False, "reason": None}
    
    def check_daily_limits(self) -> Dict:
        """检查单日限制"""
        self._maybe_reset_daily_stats()
        if self.daily_stats["trade_count"] >= self.max_daily_trades:
            return {
                "should_stop": True,
                "reason": "daily_trade_limit",
                "trade_count": self.daily_stats["trade_count"]
            }
        
        # 检查连亏
        if self.consecutive_losses >= self.max_consecutive_losses:
            return {
                "should_stop": True,
                "reason": "consecutive_losses",
                "consecutive_losses": self.consecutive_losses
            }
        
        return {"should_stop": False, "reason": None}
    
    def can_trade(self) -> Dict:
        """检查是否可以交易"""
        # 检查熔断
        cb_check = self.check_circuit_breaker()
        if cb_check["should_stop"]:
            return cb_check
        
        # 检查日间限制
        limits_check = self.check_daily_limits()
        if limits_check["should_stop"]:
            return limits_check
        
        # 检查是否暂停
        if self.is_paused:
            return {
                "should_stop": True,
                "reason": self.pause_reason
            }
        
        return {"should_stop": False, "reason": None}
    
    def record_trade(self, trade: dict):
        """记录交易"""
        self._maybe_reset_daily_stats()
        self.trade_history.append(trade)
        self.daily_stats["trade_count"] += 1
        
        pnl = trade.get("pnl", 0)
        self.daily_stats["pnl"] += pnl
        
        if pnl > 0:
            self.daily_stats["win_count"] += 1
            self.consecutive_losses = 0
        else:
            self.daily_stats["loss_count"] += 1
            self.consecutive_losses += 1
        
        # 更新盈亏百分比
        balance = trade.get("balance", 1)
        if balance > 0:
            self.daily_stats["pnl_pct"] = self.daily_stats["pnl"] / balance
    
    def reset_daily_stats(self):
        """重置日统计"""
        self.daily_stats = {
            "pnl": 0,
            "pnl_pct": 0,
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "start_time": datetime.now()
        }
    
    def resume(self):
        """恢复交易"""
        self.is_paused = False
        self.pause_reason = ""
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "daily": self.daily_stats.copy(),
            "consecutive_losses": self.consecutive_losses,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "total_trades": len(self.trade_history)
        }


class PositionManager:
    """仓位管理器"""
    
    def __init__(self):
        self.positions = {}  # {symbol: position}
        self.pending_orders = {}  # {order_id: order}
    
    def open_position(self, symbol: str, side: str, quantity: float, 
                     entry_price: float, leverage: int = 1):
        """开仓"""
        self.positions[symbol] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": entry_price,
            "leverage": leverage,
            "pnl": 0,
            "pnl_pct": 0,
            "open_time": datetime.now(),
            "stop_loss": None,
            "take_profit": None
        }
    
    def close_position(self, symbol: str, exit_price: float) -> Dict:
        """平仓"""
        if symbol not in self.positions:
            return {"success": False, "error": "No position"}
        
        pos = self.positions[symbol]
        
        # 计算盈亏
        if pos["side"].upper() == "LONG":
            pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
        else:
            pnl = (pos["entry_price"] - exit_price) * pos["quantity"]
        
        pnl_pct = pnl / (pos["entry_price"] * pos["quantity"]) * 100
        
        closed_pos = {
            **pos,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "close_time": datetime.now(),
            "duration": (datetime.now() - pos["open_time"]).total_seconds()
        }
        
        del self.positions[symbol]
        
        return {
            "success": True,
            "position": closed_pos,
            "pnl": pnl,
            "pnl_pct": pnl_pct
        }
    
    def update_position(self, symbol: str, current_price: float):
        """更新仓位盈亏"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        pos["current_price"] = current_price
        
        # 计算浮动盈亏
        if pos["side"].upper() == "LONG":
            pnl = (current_price - pos["entry_price"]) * pos["quantity"]
        else:
            pnl = (pos["entry_price"] - current_price) * pos["quantity"]
        
        pos["pnl"] = pnl
        pos["pnl_pct"] = pnl / (pos["entry_price"] * pos["quantity"]) * 100
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """获取仓位"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """是否有仓位"""
        return symbol in self.positions
    
    def set_stop_loss(self, symbol: str, stop_loss: float):
        """设置止损"""
        if symbol in self.positions:
            self.positions[symbol]["stop_loss"] = stop_loss
    
    def set_take_profit(self, symbol: str, take_profit: float):
        """设置止盈"""
        if symbol in self.positions:
            self.positions[symbol]["take_profit"] = take_profit
    
    def get_all_positions(self) -> Dict:
        """获取所有仓位"""
        return self.positions.copy()


# 测试
if __name__ == "__main__":
    # 测试风控
    config = {
        "max_position_pct": 0.1,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "max_daily_trades": 20,
        "max_consecutive_losses": 5,
        "circuit_breaker_loss_pct": 0.2
    }
    
    risk_mgr = RiskManager(config)
    
    # 测试仓位计算
    signal = {"strength": 0.8}
    balance = 10000
    price = 50000
    
    position_size = risk_mgr.calculate_position_size(signal, balance, price)
    print(f"仓位大小: {position_size:.6f} BTC")
    
    # 测试止损
    entry = 50000
    current = 49000
    
    result = risk_mgr.check_stop_loss(entry, current, "LONG")
    print(f"止损检查: {result}")
    
    # 测试止盈
    current = 52500
    result = risk_mgr.check_take_profit(entry, current, "LONG")
    print(f"止盈检查: {result}")
    
    # 测试仓位管理
    pos_mgr = PositionManager()
    pos_mgr.open_position("BTCUSDT", "LONG", 0.01, 50000, 10)
    
    pos = pos_mgr.get_position("BTCUSDT")
    print(f"当前仓位: {pos}")
    
    pos_mgr.update_position("BTCUSDT", 51000)
    pos = pos_mgr.get_position("BTCUSDT")
    print(f"更新后仓位: {pos}")
    
    result = pos_mgr.close_position("BTCUSDT", 51000)
    print(f"平仓结果: {result}")
