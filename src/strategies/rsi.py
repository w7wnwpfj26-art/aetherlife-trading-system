
import pandas as pd
import numpy as np
from .base import BaseStrategy

class RSIStrategy(BaseStrategy):
    """RSI 超买超卖策略"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "RSI策略"
        self.rsi_period = config.get("rsi_period", 14)
        self.oversold = config.get("oversold", 30)
        self.overbought = config.get("overbought", 70)
        self.params = {
            "rsi_period": self.rsi_period,
            "oversold": self.oversold,
            "overbought": self.overbought
        }
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        loss_safe = loss.replace(0, np.nan)
        rs = (gain / loss_safe).fillna(0)
        df['rsi'] = 100 - (100 / (1 + rs))
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < self.rsi_period:
            out = df.copy() if df is not None and not df.empty else pd.DataFrame()
            if not out.empty:
                out["signal"] = 0
            return out
        df = self.analyze(df)
        df["signal"] = 0
        df.loc[df["rsi"] < self.oversold, "signal"] = 1
        df.loc[df["rsi"] > self.overbought, "signal"] = -1
        return df
