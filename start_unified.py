#!/usr/bin/env python3
"""
统一入口启动脚本 - 单端口 8888 提供：首页 / 后台管理 / 前台总览 / 交易仪表盘
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ui.unified_server import create_unified_app
from aiohttp import web


async def main():
    port = 8888
    host = "127.0.0.1"
    app = create_unified_app(port=port)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    url = f"http://{host}:{port}/"
    print("")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║   AI 合约交易系统 - 统一入口 (单端口 8888)              ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print("")
    print(f"  🌐 首页:       {url}")
    print(f"  ⚙️  后台管理:   {url}admin")
    print(f"  📊 前台总览:   {url}pages/front.html")
    print(f"  📈 交易仪表盘: {url}dashboard")
    print("")
    print("  按 Ctrl+C 停止")
    print("")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
