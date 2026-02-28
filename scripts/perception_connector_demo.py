"""
感知层连接器演示脚本
展示 IBKR、Crypto、Kafka 的集成使用
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_crypto_connector():
    """演示加密货币连接器"""
    from aetherlife.perception import CryptoConnector, create_crypto_connector
    
    logger.info("=== 加密货币连接器演示 ===")
    
    try:
        # 创建连接器
        connector = await create_crypto_connector(
            exchange="binance",
            testnet=True
        )
        
        # 1. 获取快照
        logger.info("获取 BTC/USDT 快照...")
        snapshot = await connector.get_snapshot("BTC/USDT")
        if snapshot:
            logger.info(f"快照: 最新价 {snapshot.last_price}, Spread {snapshot.orderbook.spread_bps() if snapshot.orderbook else 0:.2f} bps")
        
        # 2. 订阅实时 Ticker
        logger.info("订阅实时 Ticker (10秒)...")
        
        tick_count = [0]
        
        async def on_ticker(data):
            tick_count[0] += 1
            if tick_count[0] % 5 == 0:
                logger.info(f"Ticker 更新: {data['last_price']:.2f} | Bid {data['bid_price']:.2f} | Ask {data['ask_price']:.2f}")
        
        await connector.watch_ticker("BTC/USDT", on_ticker)
        await asyncio.sleep(10)
        
        logger.info(f"收到 {tick_count[0]} 次 Ticker 更新")
        
        # 3. 订阅实时 OrderBook
        logger.info("订阅实时 OrderBook (5秒)...")
        
        ob_count = [0]
        
        async def on_orderbook(data):
            ob_count[0] += 1
            if ob_count[0] % 3 == 0:
                mid = (data['bids'][0][0] + data['asks'][0][0]) / 2 if data['bids'] and data['asks'] else 0
                logger.info(f"OrderBook 更新: Mid {mid:.2f} | Bids {len(data['bids'])} | Asks {len(data['asks'])}")
        
        await connector.watch_orderbook("BTC/USDT", limit=10, callback=on_orderbook)
        await asyncio.sleep(5)
        
        logger.info(f"收到 {ob_count[0]} 次 OrderBook 更新")
        
        await connector.close()
        logger.info("加密货币连接器演示完成")
        
    except Exception as e:
        logger.error(f"加密货币连接器演示失败: {e}", exc_info=True)


async def demo_ibkr_connector():
    """演示 IBKR 连接器"""
    from aetherlife.perception import IBKRConnector, IBKRConfig
    
    logger.info("=== IBKR 连接器演示 ===")
    
    try:
        # 创建连接器（需要先启动 TWS/Gateway）
        config = IBKRConfig(
            host="127.0.0.1",
            port=7497,  # Paper trading
            client_id=1
        )
        
        connector = IBKRConnector(config)
        
        # 尝试连接
        logger.info("连接 IBKR TWS/Gateway...")
        connected = await connector.connect()
        
        if not connected:
            logger.warning("IBKR 未连接（需要启动 TWS/Gateway），跳过演示")
            return
        
        # 1. 获取美股快照
        logger.info("获取 AAPL 快照...")
        snapshot = await connector.get_snapshot("AAPL", sec_type="STK", exchange="SMART", currency="USD")
        if snapshot:
            logger.info(f"AAPL 快照: 最新价 {snapshot.last_price}")
        
        # 2. 订阅实时行情
        logger.info("订阅 AAPL 实时行情 (5秒)...")
        
        tick_count = [0]
        
        def on_ticker(data):
            tick_count[0] += 1
            if tick_count[0] % 3 == 0:
                logger.info(f"AAPL 更新: {data['last_price']:.2f} | Bid {data['bid_price']:.2f} x {data['bid_size']}")
        
        await connector.subscribe_ticker("AAPL", callback=on_ticker)
        await asyncio.sleep(5)
        
        logger.info(f"收到 {tick_count[0]} 次行情更新")
        
        # 3. 获取 A股 快照（通过 Stock Connect）
        logger.info("获取 600000 (浦发银行) 快照...")
        a_snapshot = await connector.get_snapshot("600000", sec_type="STK", exchange="SEHK", currency="HKD")
        if a_snapshot:
            logger.info(f"600000 快照: 最新价 {a_snapshot.last_price}")
        
        await connector.close()
        logger.info("IBKR 连接器演示完成")
        
    except Exception as e:
        logger.error(f"IBKR 连接器演示失败: {e}", exc_info=True)


async def demo_kafka_pipeline():
    """演示 Kafka 数据管道"""
    from aetherlife.perception import create_data_pipeline, create_crypto_connector
    from aetherlife.perception.models import MarketSnapshot
    
    logger.info("=== Kafka 数据管道演示 ===")
    
    try:
        # 创建 Kafka 管道（需要先启动 Kafka/Redpanda）
        logger.info("连接 Kafka...")
        pipeline = await create_data_pipeline(kafka_servers="localhost:9092")
        
        # 创建加密货币连接器
        connector = await create_crypto_connector("binance", testnet=True)
        
        # 订阅数据并转发到 Kafka
        logger.info("订阅数据并转发到 Kafka (10秒)...")
        
        msg_count = [0]
        
        async def on_ticker(data):
            await pipeline.process_tick(data)
            msg_count[0] += 1
            if msg_count[0] % 5 == 0:
                logger.info(f"已转发 {msg_count[0]} 条 Tick 消息到 Kafka")
        
        async def on_orderbook(data):
            await pipeline.process_orderbook(data)
        
        await connector.watch_ticker("BTC/USDT", on_ticker)
        await connector.watch_orderbook("BTC/USDT", callback=on_orderbook)
        
        await asyncio.sleep(10)
        
        # 刷新缓冲区
        await pipeline.flush()
        
        logger.info(f"总计转发 {msg_count[0]} 条消息到 Kafka")
        
        await connector.close()
        await pipeline.kafka.close()
        logger.info("Kafka 数据管道演示完成")
        
    except Exception as e:
        logger.error(f"Kafka 数据管道演示失败: {e}", exc_info=True)


async def main():
    """主函数"""
    logger.info("AetherLife 感知层连接器演示")
    logger.info("=" * 60)
    
    # 演示加密货币连接器
    await demo_crypto_connector()
    
    await asyncio.sleep(2)
    
    # 演示 IBKR 连接器（需要 TWS/Gateway 运行）
    await demo_ibkr_connector()
    
    await asyncio.sleep(2)
    
    # 演示 Kafka 管道（需要 Kafka 运行）
    await demo_kafka_pipeline()
    
    logger.info("=" * 60)
    logger.info("所有演示完成")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断")
