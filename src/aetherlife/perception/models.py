"""感知层统一数据模型"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    CRYPTO = "crypto"
    TW_FUTURES = "tw_futures"
    US_EQUITY = "us_equity"


@dataclass
class OrderBookSlice:
    """订单簿快照（统一多交易所格式）"""
    symbol: str
    exchange: str
    bids: List[tuple]  # [(price, qty), ...]
    asks: List[tuple]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence: Optional[int] = None

    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0][0] + self.asks[0][0]) / 2

    def spread_bps(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        mid = self.mid_price()
        if mid <= 0:
            return 0.0
        return (self.asks[0][0] - self.bids[0][0]) / mid * 10_000


@dataclass
class OHLCVCandle:
    """K 线"""
    symbol: str
    exchange: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    start_time: datetime
    end_time: datetime
    interval: str  # 1m, 5m, 1h


@dataclass
class MarketSnapshot:
    """市场快照（供 Agent 一次消费）"""
    symbol: str
    exchange: str
    orderbook: Optional[OrderBookSlice] = None
    last_price: float = 0.0
    ticker_24h: Optional[dict] = None  # 24h 涨跌幅、成交量等
    candles_1m: Optional[List[OHLCVCandle]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
