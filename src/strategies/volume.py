
import pandas as pd
import numpy as np
from .base import BaseStrategy

class VolumeStrategy(BaseStrategy):
    """成交量策略"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "成交量策略"
        self.volume_ma_period = config.get("volume_ma_period", 20)
        self.volume_threshold = config.get("volume_threshold", 2)
        self.params = {
            "volume_ma_period": self.volume_ma_period,
            "volume_threshold": self.volume_threshold
        }
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 成交量均线
        df['volume_ma'] = df['volume'].rolling(self.volume_ma_period).mean()
        # 成交量放大（避免除零与 NaN）
        df['volume_ratio'] = (df['volume'] / df['volume_ma'].replace(0, np.nan)).fillna(0)
        
        # 价格变化
        df['price_change'] = df['close'].pct_change()
        df['price_change_abs'] = df['price_change'].abs()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < self.volume_ma_period:
            out = df.copy() if df is not None and not df.empty else pd.DataFrame()
            if not out.empty:
                out["signal"] = 0
            return out
        df = self.analyze(df)
        df["signal"] = 0
        df.loc[(df["volume_ratio"] > self.volume_threshold) & (df["price_change"] > 0), "signal"] = 1
        df.loc[(df["volume_ratio"] > self.volume_threshold) & (df["price_change"] < 0), "signal"] = -1
        return df
