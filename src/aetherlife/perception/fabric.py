"""
Data Fabric：对接现有 data_fetcher + 未来 WebSocket/Kafka
Phase 0：轮询拉取；Phase 1+：WebSocket 推送 + 统一 OrderBookSlice/MarketSnapshot
"""

import asyncio
from datetime import datetime
from typing import Optional, List

from .models import MarketSnapshot, OrderBookSlice, OHLCVCandle


class DataFabric:
    """统一感知层：多源数据 → MarketSnapshot"""

    def __init__(self, exchange: str = "binance", testnet: bool = True, refresh_ms: int = 500):
        self.exchange = exchange
        self.testnet = testnet
        self.refresh_ms = refresh_ms
        self._fetcher = None
        self._symbol = "BTCUSDT"

    async def _get_fetcher(self):
        if self._fetcher is None:
            from data.data_fetcher import create_data_fetcher
            self._fetcher = create_data_fetcher(self.exchange, self.testnet)
        return self._fetcher

    def set_symbol(self, symbol: str):
        self._symbol = symbol

    async def get_snapshot(self, symbol: Optional[str] = None) -> MarketSnapshot:
        """拉取当前市场快照（Phase 0 轮询；Phase 1 可改为从 WS 缓存读）"""
        sym = symbol or self._symbol
        fetcher = await self._get_fetcher()
        # 并行：订单簿 + ticker + K 线
        ob, ticker, df = await asyncio.gather(
            fetcher.get_orderbook(sym, 20),
            fetcher.get_ticker(sym),
            fetcher.get_ohlcv(sym, "1m", 60),
        )
        # 统一订单簿格式
        bids = [(float(p), float(q)) for p, q in ob.get("bids", [])[:10]]
        asks = [(float(p), float(q)) for p, q in ob.get("asks", [])[:10]]
        orderbook = OrderBookSlice(
            symbol=sym,
            exchange=self.exchange,
            bids=bids,
            asks=asks,
            timestamp=datetime.utcnow(),
        )
        last_price = float(ticker.get("last_price") or 0)
        candles: Optional[List[OHLCVCandle]] = None
        if df is not None and not df.empty and "open_time" in df.columns:
            candles = []
            for _, row in df.tail(30).iterrows():
                ts = row["open_time"]
                if hasattr(ts, "to_pydatetime"):
                    ts = ts.to_pydatetime()
                else:
                    ts = datetime.utcnow()
                candles.append(OHLCVCandle(
                    symbol=sym,
                    exchange=self.exchange,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    start_time=ts,
                    end_time=ts,
                    interval="1m",
                ))
        return MarketSnapshot(
            symbol=sym,
            exchange=self.exchange,
            orderbook=orderbook,
            last_price=last_price,
            ticker_24h=dict(ticker) if isinstance(ticker, dict) else None,
            candles_1m=candles,
            timestamp=datetime.utcnow(),
        )

    async def close(self):
        if self._fetcher:
            await self._fetcher.close()
            self._fetcher = None
