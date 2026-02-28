#!/usr/bin/env python3
"""
WebSocket 实时行情演示
用法示例：
  python3 scripts/ws_realtime_demo.py --exchange binance --symbol BTCUSDT --stream ticker
  python3 scripts/ws_realtime_demo.py --exchange okx --symbol BTC-USDT-SWAP --stream orderbook
"""

import argparse
import asyncio
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.data_fetcher import create_data_fetcher


def parse_args():
    parser = argparse.ArgumentParser(description="WebSocket 实时行情演示")
    parser.add_argument("--exchange", choices=["binance", "okx"], default="binance", help="交易所")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对")
    parser.add_argument("--stream", choices=["ticker", "orderbook"], default="ticker", help="订阅类型")
    parser.add_argument("--depth", type=int, default=5, help="订单簿深度")
    parser.add_argument("--testnet", action="store_true", help="使用测试网")
    return parser.parse_args()


async def main():
    args = parse_args()

    # OKX 默认合约格式提醒
    if args.exchange == "okx" and args.symbol == "BTCUSDT":
        args.symbol = "BTC-USDT-SWAP"

    fetcher = create_data_fetcher(args.exchange, testnet=args.testnet)

    async def on_ticker(data):
        print(f"[{data.get('symbol')}] bid={data.get('bid_price')} ask={data.get('ask_price')} last={data.get('last_price', 'N/A')}")

    async def on_orderbook(data):
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None
        print(f"[{data.get('symbol')}] best_bid={best_bid} best_ask={best_ask} depth={len(bids)}/{len(asks)}")

    try:
        if args.stream == "ticker":
            await fetcher.stream_ticker(args.symbol, on_ticker)
        else:
            await fetcher.stream_orderbook(args.symbol, args.depth, on_orderbook)
    except KeyboardInterrupt:
        print("\n已停止订阅")
    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
