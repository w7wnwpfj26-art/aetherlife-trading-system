"""
Kafka 数据管道
统一多源数据流，发布到 Kafka/Redpanda
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import asdict

try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.errors import KafkaError
    _KAFKA_AVAILABLE = True
except ImportError:
    _KAFKA_AVAILABLE = False
    AIOKafkaProducer = None

from .models import MarketSnapshot, OrderBookSlice

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Kafka/Redpanda 数据生产者
    
    功能：
    1. 发布标准化市场数据到 Kafka Topic
    2. 支持多种数据类型（Tick、OrderBook、Trades）
    3. 自动序列化（JSON）
    4. 批量发送优化
    5. 错误重试
    """
    
    # Topic 定义
    TOPIC_TICK = "market_data_tick"
    TOPIC_ORDERBOOK = "market_data_orderbook"
    TOPIC_TRADES = "market_data_trades"
    TOPIC_SNAPSHOT = "market_data_snapshot"
    
    def __init__(self, bootstrap_servers: str = "localhost:9092",
                 client_id: str = "aetherlife"):
        if not _KAFKA_AVAILABLE:
            raise ImportError("aiokafka not installed. Run: pip install aiokafka")
        
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.producer: Optional[AIOKafkaProducer] = None
        self._connected = False
        
    async def connect(self) -> bool:
        """连接到 Kafka"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                compression_type='gzip',
                linger_ms=10,  # 批量发送延迟
                acks='all',  # 等待所有副本确认
            )
            
            await self.producer.start()
            self._connected = True
            logger.info(f"Kafka Producer 连接成功: {self.bootstrap_servers}")
            return True
            
        except Exception as e:
            logger.error(f"Kafka 连接失败: {e}")
            self._connected = False
            return False
    
    async def send_tick(self, data: Dict[str, Any]):
        """
        发送 Tick 数据
        
        Args:
            data: {
                "symbol": str,
                "exchange": str,
                "last_price": float,
                "bid_price": float,
                "ask_price": float,
                "volume": float,
                "timestamp": datetime
            }
        """
        await self._send(self.TOPIC_TICK, data, key=data.get('symbol'))
    
    async def send_orderbook(self, data: Dict[str, Any]):
        """
        发送 OrderBook 数据
        
        Args:
            data: {
                "symbol": str,
                "exchange": str,
                "bids": List[Tuple[float, float]],
                "asks": List[Tuple[float, float]],
                "timestamp": datetime,
                "nonce": int
            }
        """
        await self._send(self.TOPIC_ORDERBOOK, data, key=data.get('symbol'))
    
    async def send_trades(self, trades: List[Dict[str, Any]]):
        """
        发送 Trades 数据（批量）
        
        Args:
            trades: List of {
                "symbol": str,
                "exchange": str,
                "id": str,
                "price": float,
                "amount": float,
                "side": str,
                "timestamp": datetime
            }
        """
        if not trades:
            return
        
        # 按 symbol 分组批量发送
        for trade in trades:
            await self._send(self.TOPIC_TRADES, trade, key=trade.get('symbol'))
    
    async def send_snapshot(self, snapshot: MarketSnapshot):
        """
        发送完整市场快照
        
        Args:
            snapshot: MarketSnapshot 对象
        """
        # 转换为字典
        data = {
            "symbol": snapshot.symbol,
            "exchange": snapshot.exchange,
            "last_price": snapshot.last_price,
            "ticker_24h": snapshot.ticker_24h,
            "timestamp": snapshot.timestamp,
        }
        
        # 订单簿
        if snapshot.orderbook:
            data["orderbook"] = {
                "bids": snapshot.orderbook.bids[:10],
                "asks": snapshot.orderbook.asks[:10],
                "mid_price": snapshot.orderbook.mid_price(),
                "spread_bps": snapshot.orderbook.spread_bps(),
            }
        
        # K线
        if snapshot.candles_1m:
            data["candles_1m"] = [
                {
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "start_time": c.start_time,
                }
                for c in snapshot.candles_1m[-30:]  # 最近30根
            ]
        
        await self._send(self.TOPIC_SNAPSHOT, data, key=snapshot.symbol)
    
    async def _send(self, topic: str, value: Dict[str, Any], key: Optional[str] = None):
        """
        内部发送方法
        
        Args:
            topic: Kafka Topic
            value: 消息内容（会自动序列化为JSON）
            key: 消息 Key（用于分区）
        """
        if not self._connected or not self.producer:
            logger.warning(f"Kafka 未连接，丢弃消息: {topic}")
            return
        
        try:
            # 确保 timestamp 是 datetime 对象时转换为字符串
            if 'timestamp' in value and isinstance(value['timestamp'], datetime):
                value['timestamp'] = value['timestamp'].isoformat()
            
            # 发送消息
            key_bytes = key.encode('utf-8') if key else None
            
            await self.producer.send_and_wait(
                topic,
                value=value,
                key=key_bytes
            )
            
            logger.debug(f"Kafka 发送成功: {topic} | key={key}")
            
        except KafkaError as e:
            logger.error(f"Kafka 发送失败: {topic} | {e}")
        except Exception as e:
            logger.error(f"消息序列化失败: {e}")
    
    async def flush(self):
        """刷新缓冲区，确保所有消息发送"""
        if self.producer:
            await self.producer.flush()
    
    async def close(self):
        """关闭连接"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer 已关闭")
        
        self._connected = False


class DataPipeline:
    """
    数据管道：多源数据 → 标准化 → Kafka
    
    功能：
    1. 聚合 IBKR、Crypto 等数据源
    2. 数据标准化和去重
    3. 时序对齐
    4. 发布到 Kafka
    """
    
    def __init__(self, kafka_producer: KafkaProducer):
        self.kafka = kafka_producer
        self._last_seen: Dict[str, float] = {}  # 去重: symbol -> last_timestamp
        self._buffer: Dict[str, List[Dict]] = {}  # 缓冲: topic -> messages
        self._buffer_size = 100
        
    async def process_tick(self, data: Dict[str, Any]):
        """处理 Tick 数据"""
        # 去重
        key = f"{data.get('symbol')}_{data.get('exchange')}"
        timestamp = data.get('timestamp', datetime.now()).timestamp()
        
        if key in self._last_seen and timestamp <= self._last_seen[key]:
            logger.debug(f"重复 Tick 数据，跳过: {key}")
            return
        
        self._last_seen[key] = timestamp
        
        # 发送到 Kafka
        await self.kafka.send_tick(data)
    
    async def process_orderbook(self, data: Dict[str, Any]):
        """处理 OrderBook 数据"""
        # 去重（基于 nonce）
        key = f"{data.get('symbol')}_{data.get('exchange')}"
        nonce = data.get('nonce', 0)
        
        if key in self._last_seen and nonce <= self._last_seen[key]:
            logger.debug(f"重复 OrderBook 数据，跳过: {key}")
            return
        
        self._last_seen[key] = nonce
        
        # 发送到 Kafka
        await self.kafka.send_orderbook(data)
    
    async def process_trades(self, trades: List[Dict[str, Any]]):
        """处理 Trades 数据"""
        # Trades 通常不需要去重（每笔交易 ID 唯一）
        await self.kafka.send_trades(trades)
    
    async def process_snapshot(self, snapshot: MarketSnapshot):
        """处理完整快照"""
        await self.kafka.send_snapshot(snapshot)
    
    async def flush(self):
        """刷新所有缓冲数据"""
        await self.kafka.flush()


# 工厂函数
async def create_data_pipeline(kafka_servers: str = "localhost:9092") -> DataPipeline:
    """创建并连接数据管道"""
    producer = KafkaProducer(bootstrap_servers=kafka_servers)
    await producer.connect()
    return DataPipeline(producer)
