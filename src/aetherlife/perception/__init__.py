"""
感知层 (Perception)
对接外部市场 API → 统一 MarketSnapshot
"""

from .models import MarketSnapshot, OrderBookSlice, OHLCVCandle, MarketType
from .fabric import DataFabric

# 新增连接器 (Phase 1)
try:
    from .ibkr_connector import IBKRConnector, IBKRConfig, create_ibkr_connector
    _IBKR_AVAILABLE = True
except ImportError:
    _IBKR_AVAILABLE = False
    IBKRConnector = IBKRConfig = create_ibkr_connector = None

try:
    from .crypto_connector import CryptoConnector, create_crypto_connector
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    CryptoConnector = create_crypto_connector = None

try:
    from .kafka_producer import KafkaProducer, DataPipeline, create_data_pipeline
    _KAFKA_AVAILABLE = True
except ImportError:
    _KAFKA_AVAILABLE = False
    KafkaProducer = DataPipeline = create_data_pipeline = None

__all__ = [
    "MarketSnapshot",
    "OrderBookSlice",
    "OHLCVCandle",
    "MarketType",
    "DataFabric",
    # 新增
    "IBKRConnector",
    "IBKRConfig",
    "create_ibkr_connector",
    "CryptoConnector",
    "create_crypto_connector",
    "KafkaProducer",
    "DataPipeline",
    "create_data_pipeline",
]
