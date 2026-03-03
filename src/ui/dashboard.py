"""
Web UI 服务器
提供交易仪表盘
"""

import asyncio
import json
import logging
from datetime import datetime
from aiohttp import web

logger = logging.getLogger(__name__)


class TradingDashboard:
    """交易仪表盘 Web UI"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/status', self.api_status)
        self.app.router.add_get('/api/positions', self.api_positions)
        self.app.router.add_get('/api/orders', self.api_orders)
        self.app.router.add_get('/api/stats', self.api_stats)
        self.app.router.add_post('/api/config', self.api_config)
        self.app.router.add_post('/api/order', self.api_order)
        
    async def index(self, request):
        """主页"""
        html = """
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 交易监控 - 量化系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        background: '#0f172a',
                        surface: '#1e293b',
                        primary: '#3b82f6',
                        accent: '#10b981',
                        danger: '#ef4444',
                    },
                    fontFamily: {
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                    }
                }
            }
        }
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; }
        .glass-panel {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    </style>
</head>
<body class="antialiased min-h-screen flex flex-col">

    <!-- Navbar -->
    <nav class="border-b border-gray-800 bg-surface/50 backdrop-blur-md sticky top-0 z-50">
        <div class="container mx-auto px-6 py-4 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <div class="w-8 h-8 rounded bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center text-white font-bold">AI</div>
                <span class="font-bold text-xl tracking-tight">量化<span class="text-primary">监控</span></span>
            </div>
            <div class="flex items-center space-x-4">
                <div class="flex items-center space-x-2 px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20">
                    <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                    <span class="text-xs font-medium text-green-500">系统在线</span>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-1 container mx-auto px-6 py-8">
        
        <!-- Metrics Grid -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <!-- Balance -->
            <div class="glass-panel rounded-xl p-6 relative overflow-hidden">
                <div class="absolute right-0 top-0 p-4 opacity-5">
                    <svg class="w-24 h-24" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.15-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39h-2.07c-.12-1.01-1.2-1.65-2.49-1.65-1.51 0-2.4.96-2.4 1.55 0 .76.4 1.47 2.67 2.02 2.5.6 4.17 1.66 4.17 3.66 0 1.63-1.1 2.75-2.91 3.11z"/></svg>
                </div>
                <div class="relative">
                    <p class="text-sm text-gray-400 font-medium uppercase tracking-wider">总权益 (USDT)</p>
                    <h3 class="text-3xl font-bold text-white mt-2 font-mono" id="balance">$10,000.00</h3>
                    <div class="mt-2 flex items-center text-sm text-green-500">
                        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                        <span id="pnl">+0.00%</span>
                    </div>
                </div>
            </div>

            <!-- Positions -->
            <div class="glass-panel rounded-xl p-6">
                <p class="text-sm text-gray-400 font-medium uppercase tracking-wider">当前持仓</p>
                <h3 class="text-3xl font-bold text-white mt-2" id="positions">0</h3>
                <div class="mt-2 text-sm text-gray-500">活跃合约数量</div>
            </div>

            <!-- Trades -->
            <div class="glass-panel rounded-xl p-6">
                <p class="text-sm text-gray-400 font-medium uppercase tracking-wider">今日交易</p>
                <h3 class="text-3xl font-bold text-white mt-2" id="todayTrades">0</h3>
                <div class="mt-2 text-sm text-gray-500">执行订单数</div>
            </div>

            <!-- Win Rate -->
            <div class="glass-panel rounded-xl p-6">
                <p class="text-sm text-gray-400 font-medium uppercase tracking-wider">胜率</p>
                <h3 class="text-3xl font-bold text-white mt-2" id="winRate">--%</h3>
                <div class="mt-2 text-sm text-gray-500">最近 20 笔交易</div>
            </div>
        </div>

        <!-- Charts & Controls -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <!-- Chart -->
            <div class="lg:col-span-2 glass-panel rounded-xl p-1 border border-gray-800 h-[500px] flex flex-col">
                <div class="flex justify-between items-center p-4 border-b border-gray-800">
                    <div class="flex items-center space-x-4">
                        <select id="symbolSelector" class="bg-surface border border-gray-700 rounded px-3 py-1 text-sm focus:outline-none focus:border-primary">
                            <option value="BTCUSDT">BTCUSDT</option>
                            <option value="ETHUSDT">ETHUSDT</option>
                            <option value="SOLUSDT">SOLUSDT</option>
                        </select>
                        <div class="flex space-x-1 bg-surface rounded p-1">
                            <button class="px-3 py-1 text-xs rounded hover:bg-gray-700 transition bg-gray-700 text-white">15m</button>
                            <button class="px-3 py-1 text-xs rounded hover:bg-gray-700 transition text-gray-400">1h</button>
                            <button class="px-3 py-1 text-xs rounded hover:bg-gray-700 transition text-gray-400">4h</button>
                        </div>
                    </div>
                    <div class="text-sm font-mono text-green-500" id="currentPrice">--</div>
                </div>
                <div id="chartContainer" class="flex-1 w-full h-full"></div>
            </div>

            <!-- Control Panel -->
            <div class="space-y-6">
                <!-- Manual Trade -->
                <div class="glass-panel rounded-xl p-6">
                    <h3 class="text-lg font-bold mb-4 text-white">快速交易</h3>
                    <div class="space-y-4">
                        <div>
                            <label class="text-xs text-gray-400 mb-1 block">交易对</label>
                            <div class="p-3 bg-background border border-gray-700 rounded text-sm text-white font-mono">BTCUSDT</div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <button id="btnBuy" class="py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold transition shadow-lg shadow-green-900/20">
                                买入 / 做多
                            </button>
                            <button id="btnSell" class="py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold transition shadow-lg shadow-red-900/20">
                                卖出 / 做空
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Active Strategy -->
                <div class="glass-panel rounded-xl p-6">
                    <h3 class="text-lg font-bold mb-4 text-white">策略状态</h3>
                    <div class="flex items-center justify-between mb-4">
                        <span class="text-gray-400 text-sm">当前策略</span>
                        <span class="text-primary font-medium bg-primary/10 px-3 py-1 rounded text-sm">Breakout</span>
                    </div>
                    <div class="flex items-center justify-between mb-4">
                        <span class="text-gray-400 text-sm">自动交易</span>
                        <div class="flex items-center space-x-2">
                            <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            <span class="text-green-500 text-sm">运行中</span>
                        </div>
                    </div>
                    <div class="space-y-2">
                        <div class="flex justify-between text-xs text-gray-500">
                            <span>信号强度</span>
                            <span>85%</span>
                        </div>
                        <div class="w-full bg-gray-800 rounded-full h-1.5">
                            <div class="bg-primary h-1.5 rounded-full" style="width: 85%"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="glass-panel rounded-xl p-6">
            <h3 class="text-lg font-bold mb-6 text-white">最近活动</h3>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="text-gray-400 text-xs uppercase tracking-wider border-b border-gray-800">
                            <th class="pb-3 pl-4">时间</th>
                            <th class="pb-3">交易对</th>
                            <th class="pb-3">类型</th>
                            <th class="pb-3 text-right">价格</th>
                            <th class="pb-3 text-right">数量</th>
                            <th class="pb-3 text-right">盈亏</th>
                            <th class="pb-3 text-center">状态</th>
                        </tr>
                    </thead>
                    <tbody class="text-sm divide-y divide-gray-800/50" id="orderTable">
                        <tr>
                            <td colspan="7" class="py-8 text-center text-gray-500 italic">暂无交易记录</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <script>
        // Chart Initialization
        const chartContainer = document.getElementById('chartContainer');
        const chart = LightweightCharts.createChart(chartContainer, {
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#1e293b' },
                horzLines: { color: '#1e293b' },
            },
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            timeScale: {
                borderColor: '#334155',
                timeVisible: true,
            },
            rightPriceScale: {
                borderColor: '#334155',
            },
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        // Resize chart on window resize
        window.addEventListener('resize', () => {
            chart.resize(chartContainer.clientWidth, chartContainer.clientHeight);
        });

        // Generate Mock Data
        function generateData() {
            const data = [];
            let time = Math.floor(Date.now() / 1000) - 100 * 60 * 15; // 100 candles of 15m
            let price = 50000;
            
            for (let i = 0; i < 100; i++) {
                const open = price;
                const close = price + (Math.random() - 0.5) * 200;
                const high = Math.max(open, close) + Math.random() * 50;
                const low = Math.min(open, close) - Math.random() * 50;
                
                data.push({ time, open, high, low, close });
                price = close;
                time += 60 * 15;
            }
            return data;
        }

        candleSeries.setData(generateData());

        // Live Data Update Simulation
        setInterval(async () => {
            try {
                // Fetch stats
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Update UI
                document.getElementById('balance').innerText = '$' + data.balance.toLocaleString();
                document.getElementById('positions').innerText = data.positions;
                document.getElementById('todayTrades').innerText = data.todayTrades;
                
                // Mock chart update
                const last = candleSeries.data()[candleSeries.data().length - 1];
                const newPrice = last.close + (Math.random() - 0.5) * 50;
                const now = Math.floor(Date.now() / 1000);
                
                // Update current candle or add new one
                // Simplified for demo: just updating price display
                document.getElementById('currentPrice').innerText = '$' + newPrice.toFixed(2);

            } catch (e) { console.error(e); }
        }, 2000);

        // Trade Buttons
        document.getElementById('btnBuy').onclick = async () => {
            await fetch('/api/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: 'BTCUSDT', side: 'BUY'})
            });
            alert('买单已发送');
        };

        document.getElementById('btnSell').onclick = async () => {
            await fetch('/api/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: 'BTCUSDT', side: 'SELL'})
            });
            alert('卖单已发送');
        };
    </script>
</body>
</html>
"""
        return web.Response(text=html, content_type='text/html')
    
    async def api_status(self, request):
        """API: 状态"""
        return web.json_response({
            "balance": 10000,
            "pnl": 0,
            "positions": 0,
            "todayTrades": 0,
            "winRate": 0,
            "status": "running"
        })
    
    async def api_positions(self, request):
        """API: 持仓"""
        return web.json_response([])
    
    async def api_orders(self, request):
        """API: 订单"""
        return web.json_response([])
    
    async def api_stats(self, request):
        """API: 统计"""
        return web.json_response({
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "total_pnl": 0
        })
    
    async def api_config(self, request):
        """API: 配置"""
        await request.json()
        return web.json_response({"success": True})
    
    async def api_order(self, request):
        """API: 下单"""
        await request.json()
        return web.json_response({"success": True, "order_id": "mock_order_" + datetime.now().strftime("%Y%m%d%H%M%S")})
    
    def run(self, host='0.0.0.0', port=8080):
        """运行服务器"""
        web.run_app(self.app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dashboard = TradingDashboard()
    logger.info("交易仪表盘启动: http://localhost:8080")
    dashboard.run()
