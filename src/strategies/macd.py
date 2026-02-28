
import pandas as pd
from .base import BaseStrategy

class MACrossStrategy(BaseStrategy):
    """均线交叉策略"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "均线交叉策略"
        self.fast_ma = config.get("fast_ma", 10)
        self.slow_ma = config.get("slow_ma", 50)
        self.params = {
            "fast_ma": self.fast_ma,
            "slow_ma": self.slow_ma
        }
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['fast_ma'] = df['close'].rolling(self.fast_ma).mean()
        df['slow_ma'] = df['close'].rolling(self.slow_ma).mean()
        
        # 金叉/死叉
        df['ma_diff'] = df['fast_ma'] - df['slow_ma']
        df['ma_diff_prev'] = df['ma_diff'].shift(1)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < self.slow_ma:
            out = df.copy() if df is not None and not df.empty else pd.DataFrame()
            if not out.empty:
                out["signal"] = 0
            return out
        df = self.analyze(df)
        df["signal"] = 0
        df.loc[(df["ma_diff"] > 0) & (df["ma_diff_prev"] <= 0), "signal"] = 1
        df.loc[(df["ma_diff"] < 0) & (df["ma_diff_prev"] >= 0), "signal"] = -1
        return df
