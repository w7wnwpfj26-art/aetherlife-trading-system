# AetherLife 感知层升级指南

## 📡 新增连接器（阶段1完成）

### 1. IBKR TWS API 连接器 (`ibkr_connector.py`)

#### 功能
- ✅ 连接 Interactive Brokers TWS/Gateway
- ✅ 支持股票、期货、外汇实时行情订阅
- ✅ **A股 Stock Connect** 特殊处理
- ✅ 订单簿快照获取
- ✅ 自动断线重连
- ✅ 北向额度查询（A股专用）

#### 使用示例

```python
from aetherlife.perception import IBKRConnector, IBKRConfig

# 创建配置
config = IBKRConfig(
    host="127.0.0.1",
    port=7497,  # Paper trading: 7497, Live: 7496
    client_id=1,
    readonly=True
)

# 创建连接器
connector = IBKRConnector(config)
await connector.connect()

# 订阅美股实时行情
await connector.subscribe_ticker(
    symbol="AAPL",
    sec_type="STK",
    exchange="SMART",
    currency="USD",
    callback=lambda data: print(f"AAPL: {data['last_price']}")
)

# 订阅A股（通过 Stock Connect）
await connector.subscribe_ticker(
    symbol="600000",  # 浦发银行
    sec_type="STK",
    exchange="SEHK",  # 通过香港交易所
    currency="HKD",
    callback=lambda data: print(f"600000: {data['last_price']}")
)

# 获取快照
snapshot = await connector.get_snapshot("AAPL")
print(f"Last Price: {snapshot.last_price}")

# 查询北向额度
quota = await connector.get_stock_connect_quota()
print(f"剩余额度: {quota['northbound_quota']}")

await connector.close()
```

#### 支持的证券类型

| sec_type | 说明 | exchange 示例 | currency 示例 |
|----------|------|--------------|--------------|
| STK | 股票 | SMART, SEHK, NASDAQ | USD, HKD, CNH |
| FUT | 期货 | CME, CBOT, HKFE | USD, HKD |
| CASH | 外汇 | IDEALPRO | EUR.USD |

#### 前置条件

1. 安装 TWS (Trader Workstation) 或 IB Gateway
2. 启用 API 连接：配置 → API → 启用 ActiveX 和 Socket 客户端
3. 配置端口：纸上交易 7497，实盘 7496
4. 安装依赖：`pip install ib_insync`

---

### 2. 加密货币连接器 (`crypto_connector.py`)

#### 功能
- ✅ 统一多交易所接口（Binance/Bybit/OKX）
- ✅ WebSocket 实时 Ticker 订阅
- ✅ WebSocket 实时 OrderBook 订阅
- ✅ WebSocket 实时 Trades 订阅
- ✅ 市场快照获取
- ✅ 自动重连

#### 使用示例

```python
from aetherlife.perception import CryptoConnector

# 创建连接器
connector = await create_crypto_connector(
    exchange="binance",
    testnet=True,
    api_key="your_key",  # 可选
    secret="your_secret"  # 可选
)

# 订阅 Ticker
async def on_ticker(data):
    print(f"BTC: {data['last_price']} | Spread: {data['ask_price'] - data['bid_price']}")

await connector.watch_ticker("BTC/USDT", on_ticker)

# 订阅 OrderBook
async def on_orderbook(data):
    mid = (data['bids'][0][0] + data['asks'][0][0]) / 2
    print(f"Mid Price: {mid} | Depth: {len(data['bids'])} bids, {len(data['asks'])} asks")

await connector.watch_orderbook("BTC/USDT", limit=20, callback=on_orderbook)

# 订阅 Trades
async def on_trades(trades):
    for t in trades:
        print(f"Trade: {t['side']} {t['amount']} @ {t['price']}")

await connector.watch_trades("BTC/USDT", on_trades)

# 获取快照
snapshot = await connector.get_snapshot("BTC/USDT")
print(f"Snapshot: {snapshot.last_price} | OB Spread: {snapshot.orderbook.spread_bps()} bps")

await connector.close()
```

#### 支持的交易所

| 交易所 | exchange_id | 测试网 | 主网 |
|--------|------------|-------|------|
| Binance | binance | ✅ | ✅ |
| Bybit | bybit | ✅ | ✅ |
| OKX | okx | ✅ | ✅ |

#### 前置条件

- 安装依赖：`pip install ccxt`

---

### 3. Kafka 数据管道 (`kafka_producer.py`)

#### 功能
- ✅ 统一数据流发布到 Kafka/Redpanda
- ✅ 自动序列化（JSON + Gzip 压缩）
- ✅ 数据去重和时序对齐
- ✅ 批量发送优化
- ✅ 多 Topic 分类（Tick/OrderBook/Trades/Snapshot）

#### Topic 定义

| Topic | 用途 | 数据频率 |
|-------|------|---------|
| `market_data_tick` | 实时价格 | ~100ms |
| `market_data_orderbook` | 订单簿 | ~100ms |
| `market_data_trades` | 成交记录 | 每笔成交 |
| `market_data_snapshot` | 完整快照 | 按需 |

#### 使用示例

```python
from aetherlife.perception import create_data_pipeline, create_crypto_connector

# 创建 Kafka 管道
pipeline = await create_data_pipeline(kafka_servers="localhost:9092")

# 创建数据源
connector = await create_crypto_connector("binance", testnet=True)

# 订阅并转发到 Kafka
async def on_ticker(data):
    await pipeline.process_tick(data)

async def on_orderbook(data):
    await pipeline.process_orderbook(data)

await connector.watch_ticker("BTC/USDT", on_ticker)
await connector.watch_orderbook("BTC/USDT", callback=on_orderbook)

# 运行一段时间后刷新
await asyncio.sleep(60)
await pipeline.flush()

await pipeline.kafka.close()
await connector.close()
```

#### 前置条件

1. 安装 Kafka/Redpanda：
   ```bash
   # Docker 方式
   docker run -d --name redpanda \
     -p 9092:9092 \
     vectorized/redpanda:latest \
     redpanda start --smp 1
   ```

2. 安装依赖：`pip install aiokafka`

---

## 🚀 快速开始

### 1. 安装所有依赖

```bash
cd /Users/wangqi/Documents/ai/合约交易系统
pip install -r requirements.txt
```

### 2. 运行演示脚本

```bash
# 加密货币连接器演示（不需要额外服务）
python scripts/perception_connector_demo.py

# 如果要测试 IBKR，需要先启动 TWS
# 如果要测试 Kafka，需要先启动 Kafka/Redpanda
```

### 3. 集成到 AetherLife

```python
from aetherlife.perception import (
    create_ibkr_connector,
    create_crypto_connector,
    create_data_pipeline
)

# 在 AetherLife 主循环中使用
async def enhanced_perception_layer():
    # IBKR for 股票/期货/外汇
    ibkr = await create_ibkr_connector(host="127.0.0.1", port=7497)
    
    # Crypto for 加密货币
    crypto = await create_crypto_connector("binance", testnet=True)
    
    # Kafka 统一数据流
    pipeline = await create_data_pipeline("localhost:9092")
    
    # 订阅多市场数据
    await ibkr.subscribe_ticker("AAPL", callback=lambda d: pipeline.process_tick(d))
    await crypto.watch_ticker("BTC/USDT", lambda d: pipeline.process_tick(d))
    
    # ... 运行主循环 ...
```

---

## 📋 已完成的阶段1任务

- ✅ IBKR 连接器实现（支持股票、A股、期货、外汇）
- ✅ 加密货币连接器增强（CCXT Pro WebSocket）
- ✅ Kafka 数据管道实现
- ✅ 数据标准化和去重
- ✅ 演示脚本和文档

---

## 🔜 下一步：阶段2 - 记忆层扩展

1. ClickHouse 时序数据存储
2. Redis 向量存储（记住跨市场模式）
3. 模式提取器（Lead-Lag 效应）

---

## ⚠️ 注意事项

### IBKR 限制
- 市场数据订阅需要相应的权限
- 纸上交易账户可能有延迟数据
- A股 Stock Connect 需要开通相应权限

### Kafka 生产建议
- 使用 Redpanda 而非 Kafka（更轻量）
- 配置合适的 retention 策略
- 监控 Consumer Lag

### 性能优化
- WebSocket 数据频率可能很高（>100/s）
- 建议使用 DataPipeline 的去重功能
- Kafka 批量发送减少网络开销

---

## 🐛 故障排查

### IBKR 连接失败
```
错误: ConnectionRefusedError
解决: 
1. 检查 TWS/Gateway 是否启动
2. 确认端口配置正确（7497 for paper trading）
3. 在 TWS 中启用 API 连接
```

### CCXT 连接失败
```
错误: ccxt.errors.NetworkError
解决:
1. 检查网络连接
2. 确认交易所 API 可访问
3. 使用代理（如需要）
```

### Kafka 发送失败
```
错误: KafkaTimeoutError
解决:
1. 检查 Kafka/Redpanda 是否运行
2. 确认端口 9092 可访问
3. 检查 Topic 是否自动创建
```

---

## 📖 参考文档

- [IBKR API 文档](https://interactivebrokers.github.io/tws-api/)
- [ib_insync 文档](https://ib-insync.readthedocs.io/)
- [CCXT 文档](https://docs.ccxt.com/)
- [Kafka Python 文档](https://kafka-python.readthedocs.io/)
- [Redpanda 快速开始](https://docs.redpanda.com/docs/get-started/)
