
import pandas as pd
import numpy as np
from .base import BaseStrategy

class BreakoutStrategy(BaseStrategy):
    """突破策略 - 趋势策略"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "突破策略"
        self.lookback = config.get("lookback_period", 20)
        self.threshold = config.get("threshold", 0.005)  # 0.5%突破
        self.atr_multiplier = config.get("atr_multiplier", 2)
        self.params = {
            "lookback_period": self.lookback,
            "threshold": self.threshold,
            "atr_multiplier": self.atr_multiplier
        }
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        # 移动平均线
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        
        # 最高价/最低价
        df['highest'] = df['high'].rolling(self.lookback).max()
        df['lowest'] = df['low'].rolling(self.lookback).min()
        
        # ATR (真实波幅)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(14).mean()
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['signal_line']
        
        # RSI（避免除零）
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_safe = loss.replace(0, np.nan)
        rs = (gain / loss_safe).fillna(0)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        min_len = max(50, self.lookback, 20)
        if df is None or len(df) < min_len:
            out = df.copy() if df is not None and not df.empty else pd.DataFrame()
            if not out.empty:
                out["signal"] = 0
            return out
        df = self.analyze(df)
        df["signal"] = 0
        df.loc[df["close"] > df["highest"].shift(1) * (1 + self.threshold), "signal"] = 1
        df.loc[df["close"] < df["lowest"].shift(1) * (1 - self.threshold), "signal"] = -1
        df.loc[df["rsi"] > 80, "signal"] = 0
        df.loc[df["rsi"] < 20, "signal"] = 0
        return df
