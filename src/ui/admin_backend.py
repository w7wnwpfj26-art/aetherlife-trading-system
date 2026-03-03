"""
后台管理系统 - API服务端（扩展版）
- 配置管理、策略管理、Bot控制
- AetherLife 多Agent / RL / 回测 / 执行 / 风控 管理接口
- WebSocket 实时推送 & 静态资源服务
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from aiohttp import web

# 添加父目录到路径，确保可导入项目模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from execution.exchange_client import create_client
from ui.api.aetherlife_api import AetherLifeAPI
from ui.websocket.realtime_push import RealTimePush

logger = get_logger("admin")


class AdminBackend:
    """后台管理API服务"""

    def __init__(self, bot: Any = None, orchestrator: Any = None, app: web.Application | None = None, mount_root: bool = True):
        self.bot = bot
        self.config_manager = ConfigManager()
        self.aetherlife_api = AetherLifeAPI(bot=bot, orchestrator=orchestrator)
        self.realtime = RealTimePush()
        self.app = app or web.Application()
        self._mount_root = mount_root
        self.setup_routes()

    # ------------------------------------------------------------------
    # 路由设置
    # ------------------------------------------------------------------
    def setup_routes(self):
        # 配置管理
        self.app.router.add_get('/api/config', self.get_config)
        self.app.router.add_post('/api/config/save', self.save_config)
        self.app.router.add_post('/api/config/reset', self.reset_config)
        self.app.router.add_get('/api/config/export', self.export_config)

        # API测试
        self.app.router.add_post('/api/test/connection', self.test_connection)
        self.app.router.add_post('/api/test/api', self.test_api)

        # 交易所、策略
        self.app.router.add_get('/api/exchanges', self.get_exchanges)
        self.app.router.add_get('/api/symbols', self.get_symbols)
        self.app.router.add_get('/api/strategies', self.get_strategies)

        # Bot 控制
        self.app.router.add_post('/api/bot/start', self.start_bot)
        self.app.router.add_post('/api/bot/stop', self.stop_bot)
        self.app.router.add_get('/api/bot/status', self.get_bot_status)

        # AetherLife 扩展接口
        self.app.router.add_get('/api/aetherlife/overview', self.get_aetherlife_overview)
        self.app.router.add_get('/api/aetherlife/agents', self.get_aetherlife_agents)
        self.app.router.add_get('/api/aetherlife/models', self.get_aetherlife_models)
        self.app.router.add_post('/api/aetherlife/models/load', self.load_model)
        self.app.router.add_get('/api/aetherlife/backtests', self.get_backtests)
        self.app.router.add_get('/api/aetherlife/training', self.get_training_progress)
        self.app.router.add_get('/api/aetherlife/trades', self.get_trades)
        self.app.router.add_get('/api/aetherlife/positions', self.get_positions)
        self.app.router.add_get('/api/aetherlife/risk', self.get_risk)
        self.app.router.add_get('/api/aetherlife/market', self.get_market_snapshot)
        self.app.router.add_get('/api/aetherlife/latency', self.get_latency)

        # WebSocket 实时推送
        self.app.router.add_get('/ws/realtime', self.websocket_handler)

        # 静态文件（JS/CSS）与页面
        static_dir = Path(__file__).parent / 'static'
        pages_dir = Path(__file__).parent / 'pages'
        if static_dir.exists():
            self.app.router.add_static('/static/', path=str(static_dir), name='static')
        if pages_dir.exists():
            self.app.router.add_static('/pages/', path=str(pages_dir), name='pages')

        # 管理界面
        self.app.router.add_get('/admin', self.admin_page)
        if self._mount_root:
            self.app.router.add_get('/', self.admin_page)

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------
    async def get_config(self, request):
        try:
            config = self.config_manager.load_config() or self.config_manager.get_default_config()
            safe_config = config.copy()
            if 'api_key' in safe_config:
                safe_config['api_key'] = safe_config['api_key'][:8] + '****' if safe_config['api_key'] else ''
            if 'secret_key' in safe_config:
                safe_config['secret_key'] = '****' if safe_config['secret_key'] else ''
            return web.json_response({'success': True, 'data': safe_config})
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def save_config(self, request):
        try:
            data = await request.json()
            config = data.get('config', {})
            if not config.get('exchange'):
                return web.json_response({'success': False, 'error': '交易所不能为空'}, status=400)
            success = self.config_manager.save_config(config)
            return web.json_response({'success': success, 'message': '配置保存成功' if success else '配置保存失败'}, status=200 if success else 500)
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def reset_config(self, request):
        try:
            default_config = self.config_manager.get_default_config()
            success = self.config_manager.save_config(default_config)
            return web.json_response({
                'success': success,
                'message': '配置已重置为默认值' if success else '重置失败',
                'data': default_config
            }, status=200 if success else 500)
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def export_config(self, request):
        try:
            include_sensitive = request.query.get('include_sensitive', 'false').lower() == 'true'
            config = self.config_manager.export_config(include_sensitive=include_sensitive)
            if config:
                return web.json_response({'success': True, 'data': config})
            return web.json_response({'success': False, 'error': '没有找到配置'}, status=404)
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    # ------------------------------------------------------------------
    # API 测试
    # ------------------------------------------------------------------
    async def test_connection(self, request):
        try:
            data = await request.json()
            exchange = data.get('exchange', 'binance')
            api_key = data.get('api_key', '')
            secret_key = data.get('secret_key', '')
            testnet = data.get('testnet', True)

            valid, msg = self.config_manager.validate_api_keys(exchange, api_key, secret_key, testnet)
            if not valid:
                return web.json_response({'success': False, 'error': msg}, status=400)

            try:
                client = create_client(exchange, api_key, secret_key, testnet)
                account_info = await client.get_account_info()
                if account_info:
                    return web.json_response({
                        'success': True,
                        'message': '连接成功！',
                        'data': {
                            'exchange': exchange,
                            'testnet': testnet,
                            'balance': account_info.get('totalWalletBalance', 'N/A')
                        }
                    })
                return web.json_response({'success': False, 'error': '无法获取账户信息'}, status=400)
            except Exception as e:
                return web.json_response({'success': False, 'error': f'连接失败: {str(e)}'}, status=400)
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def test_api(self, request):
        try:
            data = await request.json()
            exchange = data.get('exchange', 'binance')
            testnet = data.get('testnet', True)
            client = create_client(exchange, '', '', testnet)
            ticker = await client.get_ticker('BTCUSDT')
            if ticker:
                return web.json_response({
                    'success': True,
                    'message': '交易所API正常',
                    'data': {'exchange': exchange, 'testnet': testnet, 'price': ticker.get('lastPrice', 'N/A')}
                })
            return web.json_response({'success': False, 'error': '无法获取市场数据'}, status=400)
        except Exception as e:
            return web.json_response({'success': False, 'error': f'测试失败: {str(e)}'}, status=500)

    # ------------------------------------------------------------------
    # 基础信息
    # ------------------------------------------------------------------
    async def get_exchanges(self, request):
        exchanges = [
            {'id': 'binance', 'name': 'Binance', 'support_testnet': True, 'features': ['现货', '合约', 'API Key']},
            {'id': 'okx', 'name': 'OKX', 'support_testnet': True, 'features': ['现货', '合约', 'API Key', 'Passphrase']},
            {'id': 'bybit', 'name': 'Bybit', 'support_testnet': True, 'features': ['现货', '合约']},
            {'id': 'ibkr', 'name': 'IBKR (Stock Connect)', 'support_testnet': False, 'features': ['A股', '美股', '港股', '期货', '外汇']},
        ]
        return web.json_response({'success': True, 'data': exchanges})

    async def get_symbols(self, request):
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'HK.0700', 'SH.000300']
        return web.json_response({'success': True, 'data': symbols})

    async def get_strategies(self, request):
        strategies = [
            {'id': 'breakout', 'name': '突破策略', 'description': '价格突破+ATR趋势跟随', 'params': ['lookback_period', 'threshold', 'atr_multiplier']},
            {'id': 'grid', 'name': '网格策略', 'description': '震荡区间网格获利', 'params': ['grid_count', 'grid_size', 'base_price']},
            {'id': 'ma_cross', 'name': '均线交叉', 'description': '快慢均线交叉趋势策略', 'params': ['fast_ma', 'slow_ma']},
            {'id': 'rsi', 'name': 'RSI策略', 'description': '超买超卖反转', 'params': ['rsi_period', 'oversold', 'overbought']},
            {'id': 'volume', 'name': '成交量策略', 'description': '量能异常突破', 'params': ['volume_ma_period', 'volume_threshold']},
        ]
        return web.json_response({'success': True, 'data': strategies})

    # ------------------------------------------------------------------
    # Bot 控制
    # ------------------------------------------------------------------
    async def start_bot(self, request):
        if not self.bot:
            return web.json_response({'success': False, 'error': 'Bot实例未初始化'}, status=400)
        try:
            if getattr(self.bot, 'running', False):
                return web.json_response({'success': False, 'error': 'Bot已在运行中'}, status=400)
            asyncio.create_task(self.bot.run())
            return web.json_response({'success': True, 'message': 'Bot启动成功'})
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def stop_bot(self, request):
        if not self.bot:
            return web.json_response({'success': False, 'error': 'Bot实例未初始化'}, status=400)
        try:
            if not getattr(self.bot, 'running', False):
                return web.json_response({'success': False, 'error': 'Bot未在运行'}, status=400)
            await self.bot.stop()
            return web.json_response({'success': True, 'message': 'Bot停止成功'})
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def get_bot_status(self, request):
        if not self.bot:
            return web.json_response({'success': True, 'data': {'running': False, 'message': 'Bot未初始化'}})
        return web.json_response({
            'success': True,
            'data': {
                'running': getattr(self.bot, 'running', False),
                'exchange': getattr(self.bot, 'exchange', 'N/A'),
                'strategy': getattr(self.bot, 'strategy_name', 'N/A')
            }
        })

    # ------------------------------------------------------------------
    # AetherLife 扩展接口
    # ------------------------------------------------------------------
    async def get_aetherlife_overview(self, request):
        data = await self.aetherlife_api.get_overview()
        return web.json_response({'success': True, 'data': data})

    async def get_aetherlife_agents(self, request):
        data = await self.aetherlife_api.get_agents()
        return web.json_response({'success': True, 'data': data})

    async def get_aetherlife_models(self, request):
        data = await self.aetherlife_api.list_models()
        return web.json_response({'success': True, 'data': data})

    async def load_model(self, request):
        body = await request.json()
        model_id = body.get('model_id', '')
        result = await self.aetherlife_api.load_model(model_id)
        status = 200 if result.get('ok') else 400
        return web.json_response({'success': result.get('ok'), 'message': result.get('message')}, status=status)

    async def get_backtests(self, request):
        data = await self.aetherlife_api.get_backtests()
        return web.json_response({'success': True, 'data': data})

    async def get_training_progress(self, request):
        data = await self.aetherlife_api.get_training_progress()
        return web.json_response({'success': True, 'data': data})

    async def get_trades(self, request):
        data = await self.aetherlife_api.get_trades()
        return web.json_response({'success': True, 'data': data})

    async def get_positions(self, request):
        data = await self.aetherlife_api.get_positions()
        return web.json_response({'success': True, 'data': data})

    async def get_risk(self, request):
        data = await self.aetherlife_api.get_risk()
        return web.json_response({'success': True, 'data': data})

    async def get_market_snapshot(self, request):
        data = await self.aetherlife_api.get_market_snapshot()
        return web.json_response({'success': True, 'data': data})

    async def get_latency(self, request):
        data = await self.aetherlife_api.get_latency()
        return web.json_response({'success': True, 'data': data})

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------
    async def websocket_handler(self, request):
        return await self.realtime.handle(request)

    # ------------------------------------------------------------------
    # 页面渲染
    # ------------------------------------------------------------------
    async def admin_page(self, request):
        html = await self._load_admin_html()
        return web.Response(text=html, content_type='text/html')

    async def _load_admin_html(self) -> str:
        html_file = Path(__file__).parent / 'admin_page.html'
        if html_file.exists():
            return html_file.read_text(encoding='utf-8')
        return """
        <!DOCTYPE html>
        <html><head><title>后台管理 - AI合约交易系统</title><meta charset="UTF-8"></head>
        <body><h1>错误</h1><p>找不到管理界面文件: admin_page.html</p></body></html>
        """

    # ------------------------------------------------------------------
    # 服务启动
    # ------------------------------------------------------------------
    async def start(self, host: str = '0.0.0.0', port: int = 8080):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info("后台管理系统启动: http://%s:%s/admin", host, port)
        return runner


async def main():
    backend = AdminBackend()
    runner = await backend.start(port=8080)
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
