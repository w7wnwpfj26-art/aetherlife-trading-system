
import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.breakout import BreakoutStrategy

class TestBreakoutStrategy(unittest.TestCase):
    def setUp(self):
        self.config = {
            "lookback_period": 20,
            "threshold": 0.005,
            "atr_multiplier": 2
        }
        self.strategy = BreakoutStrategy(self.config)
        
        # Create dummy data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1min')
        self.df = pd.DataFrame({
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 105,
            'low': np.random.randn(100) + 95,
            'close': np.random.randn(100) + 100,
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)
        
        # Ensure high > low
        self.df['high'] = np.maximum(self.df['high'], self.df['close'])
        self.df['low'] = np.minimum(self.df['low'], self.df['close'])
        self.df['high'] = np.maximum(self.df['high'], self.df['open'])
        self.df['low'] = np.minimum(self.df['low'], self.df['open'])

    def test_analyze(self):
        df = self.strategy.analyze(self.df)
        self.assertIn('sma_20', df.columns)
        self.assertIn('sma_50', df.columns)
        self.assertIn('highest', df.columns)
        self.assertIn('lowest', df.columns)
        self.assertIn('atr', df.columns)
        self.assertIn('rsi', df.columns)

    def test_generate_signals(self):
        df = self.strategy.generate_signals(self.df)
        self.assertIn('signal', df.columns)
        self.assertTrue(df['signal'].isin([-1, 0, 1]).all())

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = self.strategy.generate_signals(df)
        self.assertTrue(result.empty)

if __name__ == '__main__':
    unittest.main()
