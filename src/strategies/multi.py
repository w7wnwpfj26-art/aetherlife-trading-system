
import pandas as pd
from typing import List
from .base import BaseStrategy

class MultiStrategy(BaseStrategy):
    """多策略组合"""
    
    def __init__(self, strategies: List[BaseStrategy], weights: List[float] = None):
        # 临时用空config
        super().__init__({})
        self.name = "多策略组合"
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        for strategy in self.strategies:
            df = strategy.analyze(df)
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # 为每个策略生成信号
        signal_cols = []
        for i, strategy in enumerate(self.strategies):
            df = strategy.generate_signals(df)
            df[f'signal_{i}'] = df['signal']
            signal_cols.append(f'signal_{i}')
        
        # 加权综合信号
        df['signal'] = 0
        for i, col in enumerate(signal_cols):
            df['signal'] += df[col] * self.weights[i]
        
        # 归一化到 -1, 0, 1
        df['signal'] = df['signal'].apply(lambda x: 1 if x > 0.3 else (-1 if x < -0.3 else 0))
        
        return df
