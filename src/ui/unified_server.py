"""
统一入口：单端口提供 首页 / 后台管理 / 前台总览 / 交易仪表盘
默认端口 8888：http://localhost:8888/
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

logger = logging.getLogger("unified_server")

from ui.admin_backend import AdminBackend
from ui.dashboard import TradingDashboard
from ui.dashboard_ultra import TradingDashboardUltra


def unified_index_html(port: int = 8888) -> str:
    base = f"http://localhost:{port}"
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI 合约交易系统 - 统一入口</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%%, #1e293b 100%%); min-height: 100vh; color: #f8fafc; }}
    .card {{ background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); transition: transform 0.2s, box-shadow 0.2s; }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 40px rgba(0,0,0,0.3); }}
  </style>
</head>
<body class="antialiased flex flex-col items-center justify-center p-6">
  <div class="max-w-2xl w-full text-center mb-10">
    <p class="text-blue-300/90 text-sm font-semibold uppercase tracking-wider">AetherLife · 合约交易系统</p>
    <h1 class="text-3xl md:text-4xl font-bold mt-2">统一控制台</h1>
    <p class="text-gray-400 mt-2">选择一个入口进入</p>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full max-w-6xl">
    <a href="{base}/admin" class="card rounded-2xl p-6 text-left no-underline text-inherit block">
      <div class="text-3xl mb-3">⚙️</div>
      <h2 class="text-lg font-semibold mb-1">后台管理</h2>
      <p class="text-gray-400 text-xs">配置、策略、Bot 控制</p>
    </a>
    <a href="{base}/pages/front.html" class="card rounded-2xl p-6 text-left no-underline text-inherit block">
      <div class="text-3xl mb-3">📊</div>
      <h2 class="text-lg font-semibold mb-1">前台总览</h2>
      <p class="text-gray-400 text-xs">全市场行情、信号状态</p>
    </a>
    <a href="{base}/dashboard" class="card rounded-2xl p-6 text-left no-underline text-inherit block">
      <div class="text-3xl mb-3">📈</div>
      <h2 class="text-lg font-semibold mb-1">交易仪表盘</h2>
      <p class="text-gray-400 text-xs">基础版交易界面</p>
    </a>
    <a href="{base}/ultra" class="card rounded-2xl p-6 text-left no-underline text-inherit block relative overflow-hidden group">
      <div class="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-blue-600/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
      <div class="text-3xl mb-3 relative z-10">🚀</div>
      <h2 class="text-lg font-semibold mb-1 relative z-10">Ultra 全景监控</h2>
      <p class="text-gray-400 text-xs relative z-10">核心控制室、多屏监控</p>
    </a>
  </div>
  <p class="text-gray-500 text-sm mt-10">当前地址: {base}</p>
</body>
</html>"""


def create_unified_app(port: int = 8888) -> web.Application:
    app = web.Application()
    backend = AdminBackend(app=app, mount_root=False)
    dashboard = TradingDashboard()
    # Ultra 需要 data_fetcher，但在统一入口模式下可能需要懒加载或全局共享
    # 这里暂时实例化一个无 data_fetcher 的版本，或者后续从 backend.bot 中获取
    ultra = TradingDashboardUltra(data_fetcher=backend.bot.data_fetcher if backend.bot else None)

    async def unified_index(request: web.Request) -> web.Response:
        return web.Response(text=unified_index_html(port=port), content_type="text/html")

    async def front_redirect(request: web.Request) -> web.Response:
        raise web.HTTPFound("/pages/front.html")

    app.router.add_get("/", unified_index)
    app.router.add_get("/front", front_redirect)
    
    # Dashboard 路由
    app.router.add_get("/dashboard", dashboard.index)
    app.router.add_get("/api/status", dashboard.api_status)
    app.router.add_get("/api/positions", dashboard.api_positions)
    app.router.add_get("/api/orders", dashboard.api_orders)
    app.router.add_get("/api/stats", dashboard.api_stats)
    app.router.add_post("/api/config", dashboard.api_config)
    app.router.add_post("/api/order", dashboard.api_order)
    
    # Ultra 路由 (复用 api/history 等，需要注意路由冲突，或者 Ultra 使用独立的前缀)
    # Ultra 页面
    app.router.add_get("/ultra", ultra.index)
    # Ultra API (如果与 Dashboard 冲突，需要加前缀或共用)
    # 这里 Ultra 使用了 /api/history, /api/ticker，而 Dashboard 使用了 /api/status 等，暂时没有重叠
    app.router.add_get("/api/history", ultra.api_history)
    app.router.add_get("/api/ticker", ultra.api_ticker)

    return app


async def main(host: str = "0.0.0.0", port: int = 8888, open_browser: bool = True):
    import webbrowser
    app = create_unified_app(port=port)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}/"
    logger.info("统一入口已启动: %s (首页 / 后台管理 /admin 前台 /pages/front.html 仪表盘 /dashboard)", url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main(port=8888))
