
import pandas as pd
from .base import BaseStrategy

class GridStrategy(BaseStrategy):
    """网格策略 - 震荡市场"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "网格策略"
        self.grid_count = config.get("grid_count", 10)
        self.grid_size = config.get("grid_size", 0.01)  # 1%
        self.base_price = config.get("base_price", 0)
        self.orders = []
        self.params = {
            "grid_count": self.grid_count,
            "grid_size": self.grid_size
        }
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算网格指标"""
        df = df.copy()
        
        if self.base_price == 0:
            self.base_price = df['close'].iloc[-1]
        
        # 网格价格
        df['grid_upper'] = self.base_price * (1 + self.grid_size * self.grid_count)
        df['grid_lower'] = self.base_price * (1 - self.grid_size * self.grid_count)
        
        # 计算网格线
        grid_prices = []
        for i in range(-self.grid_count, self.grid_count + 1):
            grid_prices.append(self.base_price * (1 + self.grid_size * i))
        
        df['current_grid'] = df['close'].apply(
            lambda x: min(range(len(grid_prices)), key=lambda i: abs(grid_prices[i] - x))
        )
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成网格交易信号"""
        if df is None or len(df) < 2:
            out = df.copy() if df is not None and not df.empty else pd.DataFrame()
            if not out.empty:
                out["signal"] = 0
            return out
        df = self.analyze(df)
        df["signal"] = 0
        current_price = df["close"].iloc[-1]
        last_idx = df.index[-1]
        current_grid = df["current_grid"].iloc[-1]

        grid_prices = [
            self.base_price * (1 + self.grid_size * j)
            for j in range(-self.grid_count, self.grid_count + 1)
        ]
        for i, price in enumerate(grid_prices):
            if price <= 0:
                continue
            if abs(current_price - price) / price < self.grid_size:
                # 修复: 使用 loc 精确赋值最后一行，避免覆盖整列历史信号
                if i > current_grid:   # 价格突破上方网格线 → 做多
                    df.loc[last_idx, "signal"] = 1
                else:                  # 价格跌破下方网格线 → 做空
                    df.loc[last_idx, "signal"] = -1
                break  # 只取第一个命中的网格线

        return df
