"""
加密货币连接器 (CCXT Pro WebSocket)
支持 Binance、Bybit、OKX 实时数据流
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any

try:
    import ccxt.pro as ccxtpro
    _CCXT_PRO_AVAILABLE = True
except ImportError:
    _CCXT_PRO_AVAILABLE = False
    ccxtpro = None

from .models import MarketSnapshot, OrderBookSlice, OHLCVCandle, MarketType

logger = logging.getLogger(__name__)


class CryptoConnector:
    """
    加密货币统一连接器 (基于 CCXT Pro)
    
    功能：
    1. 支持多交易所 WebSocket (Binance/Bybit/OKX)
    2. 实时 Ticker 订阅
    3. 实时 OrderBook 订阅
    4. 实时 Trades 订阅
    5. 自动重连
    """
    
    def __init__(self, exchange_id: str = "binance", testnet: bool = True,
                 api_key: str = "", secret: str = ""):
        if not _CCXT_PRO_AVAILABLE:
            raise ImportError("ccxt.pro not installed. Run: pip install ccxt")
        
        self.exchange_id = exchange_id.lower()
        self.testnet = testnet
        self.api_key = api_key
        self.secret = secret
        
        self.exchange: Optional[Any] = None
        self._connected = False
        self._watch_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        
    async def connect(self) -> bool:
        """初始化交易所连接"""
        try:
            config = {
                'enableRateLimit': True,
                'apiKey': self.api_key,
                'secret': self.secret,
            }
            
            # 测试网配置
            if self.testnet:
                if self.exchange_id == "binance":
                    config['urls'] = {
                        'api': {
                            'public': 'https://testnet.binancefuture.com',
                            'private': 'https://testnet.binancefuture.com',
                        }
                    }
                elif self.exchange_id == "bybit":
                    config['urls'] = {'api': {'public': 'https://api-testnet.bybit.com'}}
            
            # 创建交易所实例
            exchange_class = getattr(ccxtpro, self.exchange_id)
            self.exchange = exchange_class(config)
            
            # 加载市场
            await self.exchange.load_markets()
            
            self._connected = True
            logger.info(f"CCXT {self.exchange_id} 连接成功 (testnet={self.testnet})")
            return True
            
        except Exception as e:
            logger.error(f"CCXT 连接失败: {e}")
            self._connected = False
            return False
    
    async def watch_ticker(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        订阅实时 Ticker
        
        Args:
            symbol: 交易对 (如 'BTC/USDT')
            callback: 数据回调
        """
        if not self._connected:
            await self.connect()
        
        task_key = f"ticker_{symbol}"
        
        if task_key in self._watch_tasks and not self._watch_tasks[task_key].done():
            logger.warning(f"Ticker {symbol} 已在订阅中")
            return
        
        # 注册回调
        if task_key not in self._callbacks:
            self._callbacks[task_key] = []
        self._callbacks[task_key].append(callback)
        
        # 创建监听任务
        self._watch_tasks[task_key] = asyncio.create_task(
            self._ticker_loop(symbol, task_key)
        )
        
        logger.info(f"开始订阅 Ticker: {symbol}")
    
    async def _ticker_loop(self, symbol: str, task_key: str):
        """Ticker 监听循环"""
        try:
            while self._connected:
                ticker = await self.exchange.watch_ticker(symbol)
                
                # 构建标准化数据
                data = {
                    "symbol": symbol,
                    "exchange": self.exchange_id,
                    "last_price": float(ticker.get('last', 0)),
                    "bid_price": float(ticker.get('bid', 0)),
                    "ask_price": float(ticker.get('ask', 0)),
                    "bid_volume": float(ticker.get('bidVolume', 0)),
                    "ask_volume": float(ticker.get('askVolume', 0)),
                    "volume": float(ticker.get('baseVolume', 0)),
                    "quote_volume": float(ticker.get('quoteVolume', 0)),
                    "high_24h": float(ticker.get('high', 0)),
                    "low_24h": float(ticker.get('low', 0)),
                    "change_24h": float(ticker.get('change', 0)),
                    "timestamp": datetime.fromtimestamp(ticker.get('timestamp', 0) / 1000)
                }
                
                # 调用回调
                for callback in self._callbacks.get(task_key, []):
                    try:
                        await callback(data) if asyncio.iscoroutinefunction(callback) else callback(data)
                    except Exception as e:
                        logger.error(f"Ticker 回调失败 {symbol}: {e}")
                        
        except asyncio.CancelledError:
            logger.info(f"Ticker 监听取消: {symbol}")
        except Exception as e:
            logger.error(f"Ticker 监听异常 {symbol}: {e}")
            # 重连
            await asyncio.sleep(5)
            if self._connected:
                await self.connect()
    
    async def watch_orderbook(self, symbol: str, callback: Callable[[Dict[str, Any]], None], limit: int = 20):
        """
        订阅实时订单簿
        
        Args:
            symbol: 交易对
            limit: 深度档位数
            callback: 数据回调
        """
        if not self._connected:
            await self.connect()
        
        task_key = f"orderbook_{symbol}"
        
        if task_key in self._watch_tasks and not self._watch_tasks[task_key].done():
            logger.warning(f"OrderBook {symbol} 已在订阅中")
            return
        
        # 注册回调
        if task_key not in self._callbacks:
            self._callbacks[task_key] = []
        self._callbacks[task_key].append(callback)
        
        # 创建监听任务
        self._watch_tasks[task_key] = asyncio.create_task(
            self._orderbook_loop(symbol, limit, task_key)
        )
        
        logger.info(f"开始订阅 OrderBook: {symbol} (depth={limit})")
    
    async def _orderbook_loop(self, symbol: str, limit: int, task_key: str):
        """OrderBook 监听循环"""
        try:
            while self._connected:
                orderbook = await self.exchange.watch_order_book(symbol, limit)
                
                # 构建标准化数据
                data = {
                    "symbol": symbol,
                    "exchange": self.exchange_id,
                    "bids": [(float(p), float(v)) for p, v in orderbook['bids'][:limit]],
                    "asks": [(float(p), float(v)) for p, v in orderbook['asks'][:limit]],
                    "timestamp": datetime.fromtimestamp(orderbook.get('timestamp', 0) / 1000),
                    "nonce": orderbook.get('nonce', 0)
                }
                
                # 调用回调
                for callback in self._callbacks.get(task_key, []):
                    try:
                        await callback(data) if asyncio.iscoroutinefunction(callback) else callback(data)
                    except Exception as e:
                        logger.error(f"OrderBook 回调失败 {symbol}: {e}")
                        
        except asyncio.CancelledError:
            logger.info(f"OrderBook 监听取消: {symbol}")
        except Exception as e:
            logger.error(f"OrderBook 监听异常 {symbol}: {e}")
            await asyncio.sleep(5)
            if self._connected:
                await self.connect()
    
    async def watch_trades(self, symbol: str, callback: Callable[[List[Dict]], None]):
        """
        订阅实时成交记录
        
        Args:
            symbol: 交易对
            callback: 数据回调（接收 trades 列表）
        """
        if not self._connected:
            await self.connect()
        
        task_key = f"trades_{symbol}"
        
        if task_key in self._watch_tasks and not self._watch_tasks[task_key].done():
            logger.warning(f"Trades {symbol} 已在订阅中")
            return
        
        # 注册回调
        if task_key not in self._callbacks:
            self._callbacks[task_key] = []
        self._callbacks[task_key].append(callback)
        
        # 创建监听任务
        self._watch_tasks[task_key] = asyncio.create_task(
            self._trades_loop(symbol, task_key)
        )
        
        logger.info(f"开始订阅 Trades: {symbol}")
    
    async def _trades_loop(self, symbol: str, task_key: str):
        """Trades 监听循环"""
        try:
            while self._connected:
                trades = await self.exchange.watch_trades(symbol)
                
                # 构建标准化数据
                data = [{
                    "symbol": symbol,
                    "exchange": self.exchange_id,
                    "id": t.get('id', ''),
                    "price": float(t.get('price', 0)),
                    "amount": float(t.get('amount', 0)),
                    "side": t.get('side', ''),
                    "timestamp": datetime.fromtimestamp(t.get('timestamp', 0) / 1000)
                } for t in trades]
                
                # 调用回调
                for callback in self._callbacks.get(task_key, []):
                    try:
                        await callback(data) if asyncio.iscoroutinefunction(callback) else callback(data)
                    except Exception as e:
                        logger.error(f"Trades 回调失败 {symbol}: {e}")
                        
        except asyncio.CancelledError:
            logger.info(f"Trades 监听取消: {symbol}")
        except Exception as e:
            logger.error(f"Trades 监听异常 {symbol}: {e}")
            await asyncio.sleep(5)
            if self._connected:
                await self.connect()
    
    async def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        获取市场快照（单次请求）
        
        Args:
            symbol: 交易对 (如 'BTC/USDT')
        
        Returns:
            MarketSnapshot 对象或 None
        """
        if not self._connected:
            await self.connect()
        
        try:
            # 并行获取 ticker 和 orderbook
            ticker, orderbook = await asyncio.gather(
                self.exchange.fetch_ticker(symbol),
                self.exchange.fetch_order_book(symbol, limit=20)
            )
            
            # 构建订单簿
            ob = OrderBookSlice(
                symbol=symbol,
                exchange=self.exchange_id,
                bids=[(float(p), float(v)) for p, v in orderbook['bids'][:20]],
                asks=[(float(p), float(v)) for p, v in orderbook['asks'][:20]],
                timestamp=datetime.now()
            )
            
            # 构建快照
            snapshot = MarketSnapshot(
                symbol=symbol,
                exchange=self.exchange_id,
                orderbook=ob,
                last_price=float(ticker.get('last', 0)),
                ticker_24h={
                    "open": float(ticker.get('open', 0)),
                    "high": float(ticker.get('high', 0)),
                    "low": float(ticker.get('low', 0)),
                    "close": float(ticker.get('close', 0)),
                    "volume": float(ticker.get('baseVolume', 0)),
                    "quote_volume": float(ticker.get('quoteVolume', 0)),
                    "change": float(ticker.get('change', 0)),
                },
                timestamp=datetime.now()
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"获取快照失败 {symbol}: {e}")
            return None
    
    async def unsubscribe(self, task_key: str):
        """取消订阅"""
        if task_key in self._watch_tasks:
            self._watch_tasks[task_key].cancel()
            await asyncio.sleep(0.1)
            del self._watch_tasks[task_key]
            
        if task_key in self._callbacks:
            del self._callbacks[task_key]
        
        logger.info(f"取消订阅: {task_key}")
    
    async def close(self):
        """关闭连接"""
        logger.info(f"关闭 CCXT {self.exchange_id} 连接")
        
        # 取消所有监听任务
        for task in self._watch_tasks.values():
            task.cancel()
        
        # 等待任务结束
        await asyncio.gather(*self._watch_tasks.values(), return_exceptions=True)
        
        # 关闭交易所连接
        if self.exchange:
            await self.exchange.close()
        
        self._connected = False
        self._watch_tasks.clear()
        self._callbacks.clear()


# 工厂函数
async def create_crypto_connector(exchange: str = "binance", testnet: bool = True,
                                  api_key: str = "", secret: str = "") -> CryptoConnector:
    """创建并连接加密货币连接器"""
    connector = CryptoConnector(exchange, testnet, api_key, secret)
    await connector.connect()
    return connector
