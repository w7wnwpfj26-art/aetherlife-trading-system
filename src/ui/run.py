
import asyncio
import logging
import webbrowser
from aiohttp import web
import argparse
import sys
import os

# 添加父目录到路径，以便导入 data 模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入各个 UI 模块
from dashboard import TradingDashboard
from dashboard_pro import TradingDashboardPro
from dashboard_ultra import TradingDashboardUltra
from admin_backend import AdminBackend
from data.data_fetcher import create_data_fetcher

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UI_Launcher")

def parse_args():
    parser = argparse.ArgumentParser(description="启动交易系统 UI")
    parser.add_argument("--mode", type=str, default="unified", choices=["basic", "pro", "ultra", "admin", "unified"], help="UI 模式: unified(统一入口), admin, basic, pro, ultra")
    parser.add_argument("--port", type=int, help="端口号 (默认: Unified=8888, Admin=8080, Basic=8081, Pro=8082, Ultra=8088)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="主机地址")
    parser.add_argument("--exchange", type=str, default="binance", help="交易所 (binance/okx)")
    parser.add_argument("--testnet", action="store_true", default=True, help="使用测试网")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    return parser.parse_args()

async def start_server(mode, host, port, exchange, testnet, open_browser=True):
    # 自动分配端口
    if port is None:
        port_map = {
            "unified": 8888,
            "admin": 8080,
            "basic": 8081,
            "pro": 8082,
            "ultra": 8088,
        }
        port = port_map.get(mode, 8888)

    # 初始化数据获取器（unified/admin/basic 可不依赖）
    try:
        data_fetcher = create_data_fetcher(exchange, testnet)
        logger.info(f"数据源已连接: {exchange} (Testnet: {testnet})")
    except Exception as e:
        logger.error(f"数据源连接失败: {e}")
        data_fetcher = None

    app = web.Application()
    base_url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"

    # 路由配置
    if mode == "unified":
        from unified_server import create_unified_app
        app = create_unified_app(port=port)
        url = base_url + "/"
    elif mode == "admin":
        backend = AdminBackend()
        app = backend.app
        url = base_url + "/admin"
    elif mode == "basic":
        dashboard = TradingDashboard()
        app = dashboard.app
        url = base_url + "/"
    elif mode == "pro":
        dashboard = TradingDashboardPro(data_fetcher)
        app = dashboard.app
        url = base_url + "/"
    elif mode == "ultra":
        dashboard = TradingDashboardUltra(data_fetcher)
        app = dashboard.app
        url = base_url + "/"
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    
    logger.info(f"🚀 UI 服务已启动: {url}")
    logger.info(f"当前模式: {mode.upper()}")
    
    await site.start()
    
    if open_browser:
        logger.info("正在打开浏览器...")
        webbrowser.open(url)
        
    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("正在停止服务...")
    finally:
        await runner.cleanup()
        if data_fetcher:
            await data_fetcher.close()

if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(start_server(args.mode, args.host, args.port, args.exchange, args.testnet, not args.no_browser))
    except KeyboardInterrupt:
        pass
