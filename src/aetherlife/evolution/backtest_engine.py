"""
回测引擎（Backtest Engine）

在历史数据上验证策略表现：
- 支持多品种回测
- 完整的交易成本模拟（手续费、滑点）
- 详细的性能指标（Sharpe、回撤、胜率等）
- 可视化分析
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import polars as pl


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: datetime
    end_date: datetime
    initial_balance: float = 10000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    max_position: float = 1.0
    enable_shorting: bool = False


@dataclass
class Trade:
    """交易记录"""
    timestamp: datetime
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: float
    price: float
    commission: float
    slippage: float
    pnl: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""
    # 基础指标
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    
    # 交易指标
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    
    # 成本指标
    total_commission: float
    total_slippage: float
    total_cost: float
    
    # 时间序列
    equity_curve: List[float] = field(default_factory=list)
    trade_history: List[Trade] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class BacktestEngine:
    """
    回测引擎
    
    核心功能：
    1. 在历史数据上模拟交易
    2. 计算完整的性能指标
    3. 支持多策略对比
    4. 生成可视化报告
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        historical_data: pl.DataFrame,
        verbose: int = 1
    ):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
            historical_data: 历史数据（Polars DataFrame）
            verbose: 日志详细程度
        """
        self.config = config
        self.data = historical_data
        self.verbose = verbose
        
        # 状态变量
        self.balance = config.initial_balance
        self.initial_balance = config.initial_balance
        self.position = 0.0  # 当前持仓（归一化，-1到1）
        self.entry_price = 0.0
        
        # 记录
        self.equity_curve = [config.initial_balance]
        self.trade_history = []
        self.daily_returns = []
    
    def run(self, strategy_func) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy_func: 策略函数，接收(bar, position)，返回目标仓位
        
        Returns:
            回测结果
        """
        if self.verbose >= 1:
            print(f"\n{'='*60}")
            print(f"开始回测")
            print(f"时间范围: {self.config.start_date} 到 {self.config.end_date}")
            print(f"初始资金: ${self.config.initial_balance:,.2f}")
            print(f"{'='*60}\n")
        
        # 遍历历史数据
        for row in self.data.iter_rows(named=True):
            timestamp = row["timestamp"]
            price = row["close"]
            
            # 调用策略函数
            target_position = strategy_func(row, self.position)
            
            # 限制仓位
            target_position = np.clip(
                target_position,
                -self.config.max_position if self.config.enable_shorting else 0,
                self.config.max_position
            )
            
            # 执行交易
            if target_position != self.position:
                self._execute_trade(timestamp, price, target_position, row.get("symbol", "UNKNOWN"))
            
            # 更新未实现盈亏
            if self.position != 0:
                unrealized_pnl = self.position * self.balance * (price - self.entry_price) / self.entry_price
            else:
                unrealized_pnl = 0
            
            # 更新权益曲线
            current_equity = self.balance + unrealized_pnl
            self.equity_curve.append(current_equity)
            
            # 计算日收益率
            if len(self.equity_curve) > 1:
                daily_return = (current_equity - self.equity_curve[-2]) / self.equity_curve[-2]
                self.daily_returns.append(daily_return)
        
        # 计算最终指标
        result = self._calculate_metrics()
        
        if self.verbose >= 1:
            self._print_summary(result)
        
        return result
    
    def _execute_trade(
        self,
        timestamp: datetime,
        price: float,
        target_position: float,
        symbol: str
    ):
        """
        执行交易
        
        Args:
            timestamp: 时间戳
            price: 价格
            target_position: 目标仓位
            symbol: 品种
        """
        position_change = target_position - self.position
        
        # 计算交易金额
        trade_value = abs(position_change) * self.balance
        
        # 计算成本
        commission = trade_value * self.config.commission_rate
        slippage = trade_value * self.config.slippage_rate
        total_cost = commission + slippage
        
        # 扣除成本
        self.balance -= total_cost
        
        # 计算PnL（如果有持仓）
        pnl = 0.0
        if self.position != 0 and position_change != 0:
            pnl = self.position * self.balance * (price - self.entry_price) / self.entry_price
        
        # 更新仓位
        self.position = target_position
        if self.position != 0:
            self.entry_price = price
        
        # 记录交易
        action = "BUY" if position_change > 0 else "SELL"
        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            quantity=abs(position_change),
            price=price,
            commission=commission,
            slippage=slippage,
            pnl=pnl
        )
        self.trade_history.append(trade)
        
        if self.verbose >= 2:
            print(f"[{timestamp}] {action} {abs(position_change):.4f} @ ${price:.2f} | 仓位: {self.position:.2f} | 余额: ${self.balance:.2f}")
    
    def _calculate_metrics(self) -> BacktestResult:
        """计算性能指标"""
        # 总收益
        final_equity = self.equity_curve[-1]
        total_return = (final_equity - self.initial_balance) / self.initial_balance
        
        # 年化收益
        days = len(self.equity_curve)
        years = days / 252
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Sharpe Ratio
        if len(self.daily_returns) > 1:
            mean_return = np.mean(self.daily_returns)
            std_return = np.std(self.daily_returns)
            sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 最大回撤
        equity_arr = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - peak) / peak
        max_drawdown = np.min(drawdown)
        
        # Calmar Ratio
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 交易指标
        total_trades = len(self.trade_history)
        winning_trades = [t for t in self.trade_history if t.pnl > 0]
        losing_trades = [t for t in self.trade_history if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        average_win = total_wins / len(winning_trades) if winning_trades else 0
        average_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        # 成本指标
        total_commission = sum(t.commission for t in self.trade_history)
        total_slippage = sum(t.slippage for t in self.trade_history)
        total_cost = total_commission + total_slippage
        
        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=average_win,
            average_loss=average_loss,
            total_commission=total_commission,
            total_slippage=total_slippage,
            total_cost=total_cost,
            equity_curve=self.equity_curve,
            trade_history=self.trade_history,
            metadata={
                "config": self.config,
                "days": len(self.equity_curve),
                "final_equity": final_equity
            }
        )
    
    def _print_summary(self, result: BacktestResult):
        """打印回测摘要"""
        print(f"\n{'='*60}")
        print("回测结果")
        print(f"{'='*60}")
        
        print(f"\n【收益指标】")
        print(f"  总收益率: {result.total_return*100:.2f}%")
        print(f"  年化收益率: {result.annual_return*100:.2f}%")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"  最大回撤: {result.max_drawdown*100:.2f}%")
        print(f"  Calmar Ratio: {result.calmar_ratio:.2f}")
        
        print(f"\n【交易指标】")
        print(f"  总交易次数: {result.total_trades}")
        print(f"  盈利次数: {result.winning_trades}")
        print(f"  亏损次数: {result.losing_trades}")
        print(f"  胜率: {result.win_rate*100:.2f}%")
        print(f"  盈亏比: {result.profit_factor:.2f}")
        print(f"  平均盈利: ${result.average_win:.2f}")
        print(f"  平均亏损: ${result.average_loss:.2f}")
        
        print(f"\n【成本指标】")
        print(f"  总手续费: ${result.total_commission:.2f}")
        print(f"  总滑点: ${result.total_slippage:.2f}")
        print(f"  总成本: ${result.total_cost:.2f}")
        print(f"  成本占比: {result.total_cost/self.initial_balance*100:.2f}%")
        
        print(f"\n{'='*60}\n")


def compare_strategies(
    results: Dict[str, BacktestResult]
) -> pl.DataFrame:
    """
    对比多个策略的回测结果
    
    Args:
        results: 策略名 → 回测结果
    
    Returns:
        对比表格（Polars DataFrame）
    """
    rows = []
    for name, result in results.items():
        rows.append({
            "策略": name,
            "总收益": f"{result.total_return*100:.2f}%",
            "年化收益": f"{result.annual_return*100:.2f}%",
            "Sharpe": f"{result.sharpe_ratio:.2f}",
            "最大回撤": f"{result.max_drawdown*100:.2f}%",
            "胜率": f"{result.win_rate*100:.2f}%",
            "盈亏比": f"{result.profit_factor:.2f}",
            "交易次数": result.total_trades
        })
    
    df = pl.DataFrame(rows)
    return df


if __name__ == "__main__":
    from datetime import datetime, timedelta
    
    # 生成模拟历史数据
    dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(252)]
    prices = [10000 + np.random.randn() * 100 + i * 10 for i in range(252)]
    
    data = pl.DataFrame({
        "timestamp": dates,
        "close": prices,
        "symbol": ["BTCUSDT"] * 252
    })
    
    # 配置回测
    config = BacktestConfig(
        start_date=dates[0],
        end_date=dates[-1],
        initial_balance=10000,
        commission_rate=0.001,
        slippage_rate=0.0005
    )
    
    # 创建回测引擎
    engine = BacktestEngine(config, data, verbose=1)
    
    # 定义简单策略（均值回归）
    def mean_reversion_strategy(bar, current_position):
        price = bar["close"]
        # 简单均值回归：价格低于10000做多，高于12000做空
        if price < 10000:
            return 0.5  # 50%做多
        elif price > 12000:
            return -0.5 if config.enable_shorting else 0
        else:
            return 0  # 平仓
    
    # 运行回测
    result = engine.run(mean_reversion_strategy)
    
    print(f"\n最终权益: ${result.metadata['final_equity']:.2f}")
