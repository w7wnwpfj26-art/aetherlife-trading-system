"""
IBKR TWS API 连接器
使用 ib_insync 订阅股票、A股(Stock Connect)、期货、外汇实时数据
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass

try:
    from ib_insync import IB, Stock, Future, Forex, Contract, MarketOrder, LimitOrder
    from ib_insync import util as ib_util
    _IB_AVAILABLE = True
except ImportError:
    _IB_AVAILABLE = False
    IB = None
    Stock = Future = Forex = Contract = None

from .models import MarketSnapshot, OrderBookSlice, OHLCVCandle, MarketType

logger = logging.getLogger(__name__)


@dataclass
class IBKRConfig:
    """IBKR 连接配置"""
    host: str = "127.0.0.1"
    port: int = 7497  # TWS paper trading: 7497, live: 7496, Gateway paper: 4002, live: 4001
    client_id: int = 1
    readonly: bool = True
    timeout: int = 20


class IBKRConnector:
    """
    IBKR TWS API 连接器
    
    功能：
    1. 连接 TWS/Gateway
    2. 订阅实时行情（股票、期货、外汇、A股）
    3. 获取订单簿快照
    4. 处理 Stock Connect 特殊格式
    5. 断线重连
    """
    
    def __init__(self, config: Optional[IBKRConfig] = None):
        if not _IB_AVAILABLE:
            raise ImportError("ib_insync not installed. Run: pip install ib_insync")
        
        self.config = config or IBKRConfig()
        self.ib: Optional[IB] = None
        self._connected = False
        self._subscriptions: Dict[str, Contract] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._reconnect_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """连接到 IBKR TWS/Gateway"""
        try:
            if self.ib is None:
                self.ib = IB()
            
            if not self.ib.isConnected():
                await self.ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                    readonly=self.config.readonly,
                    timeout=self.config.timeout
                )
                
                # 设置断线回调
                self.ib.disconnectedEvent += self._on_disconnected
                
                self._connected = True
                logger.info(f"IBKR 连接成功: {self.config.host}:{self.config.port}")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"IBKR 连接失败: {e}")
            self._connected = False
            return False
    
    def _on_disconnected(self):
        """断线回调"""
        logger.warning("IBKR 连接断开，尝试重连...")
        self._connected = False
        
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self):
        """自动重连循环"""
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries and not self._connected:
            retry_count += 1
            await asyncio.sleep(min(retry_count * 2, 30))  # 指数退避
            
            logger.info(f"重连尝试 {retry_count}/{max_retries}")
            success = await self.connect()
            
            if success:
                # 重新订阅所有品种
                for symbol, contract in list(self._subscriptions.items()):
                    try:
                        await self._resubscribe(symbol, contract)
                    except Exception as e:
                        logger.error(f"重订阅失败 {symbol}: {e}")
                break
    
    async def _resubscribe(self, symbol: str, contract: Contract):
        """重新订阅行情"""
        if self.ib and self.ib.isConnected():
            self.ib.reqMktData(contract, "", False, False)
            logger.info(f"重新订阅: {symbol}")
    
    def create_contract(self, symbol: str, sec_type: str = "STK", 
                       exchange: str = "SMART", currency: str = "USD") -> Optional[Contract]:
        """
        创建合约对象
        
        Args:
            symbol: 股票代码（如 AAPL、600000 for A股）
            sec_type: 证券类型 STK(股票)/FUT(期货)/CASH(外汇)
            exchange: 交易所 SMART/SEHK/HKFE/CME 等
            currency: 货币 USD/HKD/CNH/CNY
        """
        try:
            if sec_type == "STK":
                # A股特殊处理：通过港交所 Stock Connect
                if symbol.startswith("6") or symbol.startswith("0") or symbol.startswith("3"):
                    # 沪深股票，使用 SEHK (Stock Connect)
                    return Stock(symbol, "SEHK", "HKD")
                else:
                    # 美股、港股等
                    return Stock(symbol, exchange, currency)
            
            elif sec_type == "FUT":
                # 期货（如 ES、NQ）
                return Future(symbol, exchange, currency)
            
            elif sec_type == "CASH":
                # 外汇（如 EURUSD）
                return Forex(symbol)
            
            return None
            
        except Exception as e:
            logger.error(f"创建合约失败 {symbol}: {e}")
            return None
    
    async def subscribe_ticker(self, symbol: str, sec_type: str = "STK",
                               exchange: str = "SMART", currency: str = "USD",
                               callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        订阅实时行情
        
        Args:
            symbol: 证券代码
            sec_type: 证券类型
            exchange: 交易所
            currency: 货币
            callback: 数据回调函数
        """
        if not self._connected or not self.ib:
            raise RuntimeError("IBKR 未连接")
        
        try:
            contract = self.create_contract(symbol, sec_type, exchange, currency)
            if not contract:
                raise ValueError(f"无法创建合约: {symbol}")
            
            # 确保合约有效
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                raise ValueError(f"合约无效: {symbol}")
            
            contract = qualified[0]
            self._subscriptions[symbol] = contract
            
            # 请求实时行情
            ticker = self.ib.reqMktData(contract, "", False, False)
            
            # 注册回调
            if callback:
                if symbol not in self._callbacks:
                    self._callbacks[symbol] = []
                self._callbacks[symbol].append(callback)
                
                # 绑定 ticker 更新事件
                ticker.updateEvent += lambda t: self._on_ticker_update(symbol, t)
            
            logger.info(f"订阅成功: {symbol} ({sec_type})")
            
        except Exception as e:
            logger.error(f"订阅失败 {symbol}: {e}")
            raise
    
    def _on_ticker_update(self, symbol: str, ticker):
        """行情更新回调"""
        try:
            data = {
                "symbol": symbol,
                "last_price": float(ticker.last) if ticker.last else 0,
                "bid_price": float(ticker.bid) if ticker.bid else 0,
                "ask_price": float(ticker.ask) if ticker.ask else 0,
                "bid_size": float(ticker.bidSize) if ticker.bidSize else 0,
                "ask_size": float(ticker.askSize) if ticker.askSize else 0,
                "volume": float(ticker.volume) if ticker.volume else 0,
                "timestamp": datetime.now(),
            }
            
            # 调用所有回调
            for callback in self._callbacks.get(symbol, []):
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"回调执行失败 {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"处理行情更新失败 {symbol}: {e}")
    
    async def get_snapshot(self, symbol: str, sec_type: str = "STK",
                          exchange: str = "SMART", currency: str = "USD") -> Optional[MarketSnapshot]:
        """
        获取市场快照（单次）
        
        Returns:
            MarketSnapshot 对象或 None
        """
        if not self._connected or not self.ib:
            await self.connect()
        
        try:
            contract = self.create_contract(symbol, sec_type, exchange, currency)
            if not contract:
                return None
            
            # 请求快照
            ticker = self.ib.reqMktData(contract, "", True, False)  # snapshot=True
            
            # 等待数据
            await asyncio.sleep(1)
            
            # 构建快照
            orderbook = None
            if ticker.bid and ticker.ask:
                orderbook = OrderBookSlice(
                    symbol=symbol,
                    exchange=exchange,
                    bids=[(float(ticker.bid), float(ticker.bidSize or 0))],
                    asks=[(float(ticker.ask), float(ticker.askSize or 0))],
                    timestamp=datetime.now()
                )
            
            snapshot = MarketSnapshot(
                symbol=symbol,
                exchange=exchange,
                orderbook=orderbook,
                last_price=float(ticker.last or 0),
                ticker_24h={
                    "open": float(ticker.open or 0),
                    "high": float(ticker.high or 0),
                    "low": float(ticker.low or 0),
                    "close": float(ticker.close or 0),
                    "volume": float(ticker.volume or 0),
                },
                timestamp=datetime.now()
            )
            
            # 取消订阅快照
            self.ib.cancelMktData(contract)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"获取快照失败 {symbol}: {e}")
            return None
    
    async def get_stock_connect_quota(self) -> Dict[str, float]:
        """
        获取 Stock Connect 北向额度（沪深港通）
        
        Returns:
            {"northbound_quota": 剩余额度, "total_quota": 总额度}
        """
        # IBKR 通过特定合约查询额度
        # 这里返回模拟数据，实际需要调用 IBKR API
        return {
            "northbound_quota": 50000000000,  # 500亿人民币
            "total_quota": 52000000000
        }
    
    async def close(self):
        """关闭连接"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("IBKR 连接已关闭")
        
        self._connected = False
        self._subscriptions.clear()
        self._callbacks.clear()
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self.ib is not None and self.ib.isConnected()


# 工厂函数
async def create_ibkr_connector(host: str = "127.0.0.1", port: int = 7497,
                                client_id: int = 1) -> IBKRConnector:
    """创建并连接 IBKR 连接器"""
    config = IBKRConfig(host=host, port=port, client_id=client_id)
    connector = IBKRConnector(config)
    await connector.connect()
    return connector
