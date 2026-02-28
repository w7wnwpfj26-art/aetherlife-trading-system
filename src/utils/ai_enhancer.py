"""
AI 增强模块
整合机器学习、情绪分析、多Agent协作
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import json


class SentimentAnalyzer:
    """情绪分析器 - 整合Twitter/新闻情绪"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        
    async def analyze_symbol(self, symbol: str) -> Dict:
        """分析 symbol 情绪 (-1 到 1)"""
        # 这里可以接入 Twitter API 或 News API
        # 暂时返回模拟数据
        return {
            "sentiment": 0.0,  # -1 极度恐慌, 0 中性, 1 极度贪婪
            "twitter_mentions": 0,
            "news_score": 0.0,
            "fear_greed_index": 50,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_fear_greed_index(self) -> int:
        """获取恐慌贪婪指数"""
        # 可以接入 alternative.me API
        return 50


class MLPredictor:
    """机器学习预测器 - 基于 FreqAI 思路"""
    
    def __init__(self, model_type: str = "lightgbm"):
        self.model = None
        self.model_type = model_type
        self.is_trained = False
        self.feature_names = [
            "rsi", "macd", "bb_position", "volume_ratio",
            "price_change", "atr", "sentiment"
        ]
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        features = pd.DataFrame()
        
        # RSI（避免除零）
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_safe = loss.replace(0, np.nan)
        rs = (gain / loss_safe).fillna(0)
        features["rsi"] = 100 - (100 / (1 + rs))
        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        features["macd"] = exp1 - exp2
        # 布林带位置（避免除零）
        bb_middle = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std().replace(0, np.nan)
        features["bb_position"] = ((df["close"] - bb_middle) / (2 * bb_std)).fillna(0)
        # 成交量比率
        vol_ma = df["volume"].rolling(20).mean().replace(0, np.nan)
        features["volume_ratio"] = (df["volume"] / vol_ma).fillna(0)
        
        # 价格变化
        features['price_change'] = df['close'].pct_change()
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        features['atr'] = true_range.rolling(14).mean()
        
        return features.fillna(0)
    
    def create_labels(self, df: pd.DataFrame, threshold: float = 0.02) -> pd.Series:
        """创建标签 (未来收益)"""
        future_returns = df['close'].shift(-10) / df['close'] - 1
        labels = pd.Series(0.0, index=df.index)
        labels[future_returns > threshold] = 1
        labels[future_returns < -threshold] = -1
        labels[future_returns.isna()] = np.nan  # 末尾无未来数据
        return labels
    
    def train(self, df: pd.DataFrame):
        """训练模型"""
        features = self.prepare_features(df)
        labels = self.create_labels(df)
        # 丢弃末尾无未来收益的样本
        valid = labels.notna()
        features = features[valid]
        labels = labels[valid].astype(int)
        if len(labels) < 30:
            return
        from sklearn.linear_model import LogisticRegression
        self.model = LogisticRegression(max_iter=1000)
        self.model.fit(features, labels)
        self.is_trained = True
        print(f"模型训练完成，准确率: {self.model.score(features, labels):.2%}")
    
    def predict(self, df: pd.DataFrame) -> float:
        """预测信号 (-1~1 置信度)"""
        if not self.is_trained or self.model is None:
            return 0.0
        features = self.prepare_features(df)
        X = features.iloc[-1:]
        if X.isna().any(axis=1).iloc[0]:
            return 0.0
        proba = self.model.predict_proba(X)
        classes = self.model.classes_
        p = proba[0]
        idx_buy = int(np.where(classes == 1)[0][0]) if 1 in classes else (1 if len(p) > 1 else 0)
        idx_sell = int(np.where(classes == -1)[0][0]) if -1 in classes else 0
        if idx_buy >= len(p) or idx_sell >= len(p):
            return 0.0
        return float(p[idx_buy] - p[idx_sell])


class MultiAgentCoordinator:
    """多Agent协调器 - 参考 Gigabrain"""
    
    def __init__(self):
        self.agents = {
            "microstructure": None,    # 订单簿分析
            "technical": None,         # 技术分析
            "fundamental": None,       # 基本面分析
            "sentiment": None,         # 情绪分析
            "onchain": None,           # 链上数据
            "news": None,              # 新闻分析
            "social": None             # 社交媒体
        }
        self.weights = {
            "microstructure": 0.15,
            "technical": 0.25,
            "fundamental": 0.15,
            "sentiment": 0.15,
            "onchain": 0.10,
            "news": 0.10,
            "social": 0.10
        }
    
    async def analyze(self, symbol: str, market_data: Dict) -> Dict:
        """多维度分析"""
        signals = {}
        
        # 1. 订单簿分析
        signals["microstructure"] = self._analyze_orderbook(
            market_data.get("orderbook", {})
        )
        
        # 2. 技术分析
        signals["technical"] = self._analyze_technical(
            market_data.get("df", pd.DataFrame())
        )
        
        # 3. 基本面
        signals["fundamental"] = await self._analyze_fundamental(symbol)
        
        # 4. 情绪
        signals["sentiment"] = await self._analyze_sentiment(symbol)
        
        # 5. 链上数据
        signals["onchain"] = await self._analyze_onchain(symbol)
        
        # 综合信号
        combined_signal = 0.0
        for agent, signal in signals.items():
            combined_signal += signal * self.weights.get(agent, 0)
        
        return {
            "signals": signals,
            "combined": combined_signal,
            "decision": "BUY" if combined_signal > 0.2 else ("SELL" if combined_signal < -0.2 else "HOLD")
        }
    
    def _analyze_orderbook(self, orderbook: Dict) -> float:
        """订单簿分析"""
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        if not bids or not asks:
            return 0.0
        
        # 计算买卖压力
        bid_volume = sum(q for _, q in bids[:5])
        ask_volume = sum(q for _, q in asks[:5])
        
        if bid_volume + ask_volume == 0:
            return 0.0
        
        pressure = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        return pressure  # -1 到 1
    
    def _analyze_technical(self, df: pd.DataFrame) -> float:
        """技术分析"""
        if df.empty or len(df) < 20:
            return 0.0
        
        signal = 0.0
        
        # RSI
        rsi = self._calculate_rsi(df)
        if rsi < 30:
            signal += 0.3  # 超卖
        elif rsi > 70:
            signal -= 0.3  # 超买
        
        # MACD
        macd = self._calculate_macd(df)
        if macd > 0:
            signal += 0.2
        else:
            signal -= 0.2
        
        # 趋势
        sma20 = df['close'].rolling(20).mean()
        sma50 = df['close'].rolling(50).mean()
        if sma20.iloc[-1] > sma50.iloc[-1]:
            signal += 0.2
        else:
            signal -= 0.2
        
        return max(-1, min(1, signal))
    
    async def _analyze_fundamental(self, symbol: str) -> float:
        """基本面分析"""
        # 可以接入 CoinGecko API
        return 0.0
    
    async def _analyze_sentiment(self, symbol: str) -> float:
        """情绪分析"""
        # 可以接入 Twitter API
        return 0.0
    
    async def _analyze_onchain(self, symbol: str) -> float:
        """链上数据分析"""
        # 可以接入 DeFiLlama, Dune Analytics
        return 0.0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        loss_safe = loss.replace(0, np.nan)
        rs = (gain / loss_safe).fillna(0)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val) if pd.notna(val) else 50.0
    
    def _calculate_macd(self, df: pd.DataFrame) -> float:
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.iloc[-1] - signal.iloc[-1]


class AutoCompoundManager:
    """自动复利管理器 - Web4.0 思路"""
    
    def __init__(self, config: dict):
        self.enabled = config.get("auto_compound", False)
        self.rebalance_threshold = config.get("rebalance_threshold", 0.1)  # 10% 利润
        self.compound_ratio = config.get("compound_ratio", 0.5)  # 50% 利润复投
        self.initial_capital = config.get("initial_capital", 10000)
        self.current_capital = self.initial_capital
        self.total_profit = 0
        
    def record_profit(self, profit: float):
        """记录利润"""
        self.total_profit += profit
        self.current_capital += profit
        
    def should_compound(self) -> bool:
        """是否应该复利"""
        if not self.enabled:
            return False
        
        profit_ratio = (self.current_capital - self.initial_capital) / self.initial_capital
        return profit_ratio >= self.rebalance_threshold
    
    def get_compound_amount(self) -> float:
        """获取复利金额"""
        if not self.should_compound():
            return 0
        
        compound = self.current_capital * self.compound_ratio
        return compound
    
    def compound(self) -> float:
        """执行复利"""
        amount = self.get_compound_amount()
        if amount > 0:
            self.initial_capital += amount
            print(f"🔄 复利投入: {amount:.2f} USDT")
        return amount
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "total_profit": self.total_profit,
            "profit_ratio": (self.current_capital - self.initial_capital) / self.initial_capital
        }


# 测试
if __name__ == "__main__":
    async def test():
        # 测试多Agent
        coordinator = MultiAgentCoordinator()
        
        # 模拟市场数据
        import numpy as np
        df = pd.DataFrame({
            'close': np.random.uniform(45000, 55000, 100),
            'high': np.random.uniform(50000, 60000, 100),
            'low': np.random.uniform(40000, 50000, 100),
            'volume': np.random.uniform(1000, 5000, 100)
        })
        
        orderbook = {
            "bids": [[50000, 1], [49999, 2], [49998, 3]],
            "asks": [[50001, 1], [50002, 2], [50003, 3]]
        }
        
        result = await coordinator.analyze("BTCUSDT", {"df": df, "orderbook": orderbook})
        
        print("多Agent分析结果:")
        print(f"综合信号: {result['combined']:.3f}")
        print(f"决策: {result['decision']}")
        
        # 测试复利
        compound_mgr = AutoCompoundManager({
            "auto_compound": True,
            "rebalance_threshold": 0.1,
            "compound_ratio": 0.5,
            "initial_capital": 10000
        })
        
        compound_mgr.record_profit(1500)  # 15% 利润
        print(f"\n利润: {compound_mgr.total_profit}")
        print(f"应复利: {compound_mgr.should_compound()}")
        print(f"复利金额: {compound_mgr.get_compound_amount():.2f}")
    
    asyncio.run(test())
