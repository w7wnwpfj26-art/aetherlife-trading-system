"""
认知层多 Agent 演示脚本
展示 7 个专业化 Agent 的协作决策
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aetherlife.cognition import (
    EnhancedOrchestrator,
    Market,
    ChinaAStockAgent,
    GlobalStockAgent,
    CryptoNanoAgent,
    CrossMarketLeadLagAgent,
    SentimentAgent
)
from aetherlife.perception import MarketSnapshot, OrderBookSlice
from aetherlife.memory import MemoryStore
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_single_agent():
    """演示单个 Agent 的决策"""
    logger.info("=== 单个 Agent 演示 ===")
    
    # 1. ChinaAStockAgent - A股专家
    logger.info("\n1. ChinaAStockAgent (A股专家)")
    
    a_stock_agent = ChinaAStockAgent()
    
    # 模拟 A股快照
    snapshot = MarketSnapshot(
        symbol="600000",  # 浦发银行
        exchange="SEHK",
        last_price=10.5,
        orderbook=OrderBookSlice(
            symbol="600000",
            exchange="SEHK",
            bids=[(10.48, 1000), (10.47, 2000), (10.46, 1500)],
            asks=[(10.52, 800), (10.53, 1200), (10.54, 1000)],
            timestamp=datetime.now()
        ),
        timestamp=datetime.now()
    )
    
    intent = await a_stock_agent.run(snapshot, "")
    logger.info(f"决策: {intent.action} | 仓位: {intent.quantity_pct:.2%} | 理由: {intent.reason} | 置信度: {intent.confidence:.2f}")
    
    # 2. CryptoNanoAgent - 加密货币专家
    logger.info("\n2. CryptoNanoAgent (加密货币专家)")
    
    crypto_agent = CryptoNanoAgent()
    
    # 模拟 BTC 快照
    snapshot = MarketSnapshot(
        symbol="BTC/USDT",
        exchange="binance",
        last_price=65000,
        orderbook=OrderBookSlice(
            symbol="BTC/USDT",
            exchange="binance",
            bids=[(64995, 0.5), (64990, 1.2), (64985, 0.8)],
            asks=[(65005, 0.3), (65010, 0.9), (65015, 0.6)],
            timestamp=datetime.now()
        ),
        timestamp=datetime.now()
    )
    
    intent = await crypto_agent.run(snapshot, "")
    logger.info(f"决策: {intent.action} | 仓位: {intent.quantity_pct:.2%} | 理由: {intent.reason} | 置信度: {intent.confidence:.2f}")
    
    # 3. GlobalStockAgent - 美股专家
    logger.info("\n3. GlobalStockAgent (美股专家)")
    
    global_agent = GlobalStockAgent()
    
    # 模拟 AAPL 快照
    snapshot = MarketSnapshot(
        symbol="AAPL",
        exchange="NASDAQ",
        last_price=175.50,
        orderbook=OrderBookSlice(
            symbol="AAPL",
            exchange="NASDAQ",
            bids=[(175.48, 100), (175.46, 200), (175.44, 150)],
            asks=[(175.52, 80), (175.54, 120), (175.56, 100)],
            timestamp=datetime.now()
        ),
        timestamp=datetime.now()
    )
    
    intent = await global_agent.run(snapshot, "")
    logger.info(f"决策: {intent.action} | 仓位: {intent.quantity_pct:.2%} | 理由: {intent.reason} | 置信度: {intent.confidence:.2f}")
    
    # 4. SentimentAgent - 情绪分析专家
    logger.info("\n4. SentimentAgent (情绪分析专家)")
    
    sentiment_agent = SentimentAgent()
    
    # 带情绪数据的 context
    context = "sentiment: 0.75 | 新闻: BTC突破新高 | Twitter热度: 极高"
    
    intent = await sentiment_agent.run(snapshot, context)
    logger.info(f"决策: {intent.action} | 仓位: {intent.quantity_pct:.2%} | 理由: {intent.reason} | 置信度: {intent.confidence:.2f}")


async def demo_orchestrator():
    """演示 Orchestrator 多 Agent 协作"""
    logger.info("\n\n=== Orchestrator 多 Agent 协作演示 ===")
    
    # 创建 Orchestrator
    orchestrator = EnhancedOrchestrator(
        enable_specialized_agents=True,
        debate_enabled=False
    )
    
    # 创建记忆存储
    memory = MemoryStore(max_events=100)
    
    # 测试场景1：加密货币（BTC）
    logger.info("\n场景1：加密货币 BTC/USDT")
    
    snapshot = MarketSnapshot(
        symbol="BTC/USDT",
        exchange="binance",
        last_price=65000,
        orderbook=OrderBookSlice(
            symbol="BTC/USDT",
            exchange="binance",
            bids=[(64995, 1.5), (64990, 2.0), (64985, 1.2)],
            asks=[(65005, 0.8), (65010, 1.0), (65015, 0.9)],
            timestamp=datetime.now()
        ),
        timestamp=datetime.now()
    )
    
    final_intent = await orchestrator.run(snapshot, memory, market=Market.CRYPTO)
    
    logger.info(f"\n最终决策:")
    logger.info(f"  动作: {final_intent.action}")
    logger.info(f"  市场: {final_intent.market}")
    logger.info(f"  仓位: {final_intent.quantity_pct:.2%}")
    logger.info(f"  理由: {final_intent.reason}")
    logger.info(f"  置信度: {final_intent.confidence:.2f}")
    if final_intent.metadata:
        logger.info(f"  元数据: {final_intent.metadata}")
    
    # 测试场景2：A股
    logger.info("\n\n场景2：中国A股 600000 (浦发银行)")
    
    snapshot = MarketSnapshot(
        symbol="600000",
        exchange="SEHK",
        last_price=10.5,
        orderbook=OrderBookSlice(
            symbol="600000",
            exchange="SEHK",
            bids=[(10.48, 5000), (10.47, 3000), (10.46, 2000)],
            asks=[(10.52, 2000), (10.53, 2500), (10.54, 3000)],
            timestamp=datetime.now()
        ),
        ticker_24h={
            "open": 10.3,
            "high": 10.6,
            "low": 10.2,
            "close": 10.45,
            "volume": 1000000
        },
        timestamp=datetime.now()
    )
    
    final_intent = await orchestrator.run(snapshot, memory, market=Market.A_STOCK)
    
    logger.info(f"\n最终决策:")
    logger.info(f"  动作: {final_intent.action}")
    logger.info(f"  市场: {final_intent.market}")
    logger.info(f"  仓位: {final_intent.quantity_pct:.2%}")
    logger.info(f"  理由: {final_intent.reason}")
    logger.info(f"  置信度: {final_intent.confidence:.2f}")
    if final_intent.metadata:
        logger.info(f"  元数据: {final_intent.metadata}")


async def demo_agent_weights():
    """演示动态调整 Agent 权重"""
    logger.info("\n\n=== Agent 权重动态调整演示 ===")
    
    orchestrator = EnhancedOrchestrator(enable_specialized_agents=True)
    memory = MemoryStore(max_events=100)
    
    snapshot = MarketSnapshot(
        symbol="BTC/USDT",
        exchange="binance",
        last_price=65000,
        orderbook=OrderBookSlice(
            symbol="BTC/USDT",
            exchange="binance",
            bids=[(64995, 1.0), (64990, 1.5)],
            asks=[(65005, 0.8), (65010, 1.2)],
            timestamp=datetime.now()
        ),
        timestamp=datetime.now()
    )
    
    # 默认权重
    logger.info("\n1. 默认权重决策")
    intent1 = await orchestrator.run(snapshot, memory)
    logger.info(f"决策: {intent1.action} | 置信度: {intent1.confidence:.2f}")
    
    # 提高情绪分析 Agent 权重
    logger.info("\n2. 提高情绪分析 Agent 权重 (1.0 -> 2.0)")
    orchestrator.update_agent_weights("sentiment", 2.0)
    
    intent2 = await orchestrator.run(snapshot, memory)
    logger.info(f"决策: {intent2.action} | 置信度: {intent2.confidence:.2f}")
    
    # 降低加密货币市场权重
    logger.info("\n3. 降低加密货币市场权重 (1.0 -> 0.6)")
    orchestrator.update_market_weights(Market.CRYPTO, 0.6)
    
    intent3 = await orchestrator.run(snapshot, memory)
    logger.info(f"决策: {intent3.action} | 置信度: {intent3.confidence:.2f}")


async def main():
    """主函数"""
    logger.info("AetherLife 认知层多 Agent 演示")
    logger.info("=" * 60)
    
    # 演示单个 Agent
    await demo_single_agent()
    
    await asyncio.sleep(1)
    
    # 演示 Orchestrator
    await demo_orchestrator()
    
    await asyncio.sleep(1)
    
    # 演示权重调整
    await demo_agent_weights()
    
    logger.info("\n" + "=" * 60)
    logger.info("所有演示完成")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断")
