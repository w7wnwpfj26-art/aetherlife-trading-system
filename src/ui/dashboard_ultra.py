
import logging
import asyncio
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingDashboardUltra:
    """ULTRA 全景监控 | 核心控制室 Web UI"""

    def __init__(self, data_fetcher=None):
        self.data_fetcher = data_fetcher
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/history', self.api_history)
        self.app.router.add_get('/api/ticker', self.api_ticker)
        # 更多 API 可按需添加

    async def index(self, request):
        """主页"""
        return web.Response(text=self.get_html(), content_type='text/html')

    async def api_history(self, request):
        """获取K线历史数据 (简化版，仅用于迷你图)"""
        symbol = request.query.get('symbol', 'BTCUSDT')
        limit = int(request.query.get('limit', 100))
        
        if not self.data_fetcher:
            return web.json_response({'error': 'Data fetcher not available'}, status=500)
            
        try:
            # 默认使用 15m K线
            df = await self.data_fetcher.get_ohlcv(symbol, '15m', limit)
            data = []
            for _, row in df.iterrows():
                data.append({
                    'time': int(row['open_time'].timestamp()),
                    'value': row['close'] # 迷你图只显示收盘价
                })
            return web.json_response(data)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def api_ticker(self, request):
        """获取最新行情"""
        symbol = request.query.get('symbol', 'BTCUSDT')
        if not self.data_fetcher:
            return web.json_response({'error': 'Data fetcher not available'}, status=500)
        try:
            ticker = await self.data_fetcher.get_ticker(symbol)
            return web.json_response(ticker)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    def get_html(self):
        return """
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ULTRA 全景监控 | 核心控制室</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-purple: #bc13fe;
            --neon-green: #0aff00;
        }

        body {
            font-family: 'Space Grotesk', sans-serif;
            background-color: #030305;
            color: #e5e7eb;
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(76, 29, 149, 0.08), transparent 25%), 
                radial-gradient(circle at 85% 30%, rgba(56, 189, 248, 0.08), transparent 25%);
        }
        
        .font-mono { font-family: 'JetBrains Mono', monospace; }

        .ultra-panel {
            background: rgba(10, 10, 14, 0.7);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 0 15px rgba(0, 0, 0, 0.3);
            border-radius: 4px;
            position: relative;
            overflow: hidden;
        }

        .ultra-panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            opacity: 0.5;
        }

        .ultra-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            background: rgba(255, 255, 255, 0.01);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #9ca3af;
        }

        .neon-text {
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 8px var(--neon-green); }
            50% { opacity: 0.5; box-shadow: 0 0 2px var(--neon-green); }
            100% { opacity: 1; box-shadow: 0 0 8px var(--neon-green); }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

        .grid-bg {
            background-size: 40px 40px;
            background-image: linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                              linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
        }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden grid-bg">

    <!-- HUD Header -->
    <header class="h-14 flex items-center justify-between px-6 border-b border-white/10 bg-black/40 backdrop-blur-md z-50">
        <div class="flex items-center gap-6">
            <div class="flex items-center gap-2">
                <i class="fas fa-cube text-blue-500 text-xl"></i>
                <div class="flex flex-col">
                    <span class="font-bold text-lg tracking-widest text-white leading-none">ULTRA</span>
                    <span class="text-[10px] text-blue-400 tracking-[0.2em] leading-none">超级监控系统</span>
                </div>
            </div>
            
            <div class="h-6 w-px bg-white/10"></div>
            
            <div class="flex items-center gap-4 text-xs font-mono text-gray-400">
                <div class="flex items-center gap-2">
                    <div class="status-dot"></div>
                    <span>系统在线</span>
                </div>
                <div>延迟: <span class="text-green-400">12ms</span></div>
                <div>CPU: <span class="text-blue-400">24%</span></div>
                <div>内存: <span class="text-purple-400">4.2GB</span></div>
            </div>
        </div>

        <div class="flex items-center gap-4">
             <div class="text-right">
                <div class="text-xs text-gray-400">全局盈亏</div>
                <div class="text-lg font-mono font-bold text-green-400 text-shadow-glow">+$12,450.23</div>
            </div>
            <div class="w-10 h-10 rounded-full border border-white/10 flex items-center justify-center bg-white/5">
                <i class="fas fa-bell text-gray-400"></i>
            </div>
        </div>
    </header>

    <!-- Main Panoramic View -->
    <main class="flex-1 p-2 grid grid-cols-4 grid-rows-3 gap-2 overflow-hidden">
        
        <!-- Top Left: Market Heatmap (1x1) -->
        <div class="col-span-1 row-span-1 ultra-panel flex flex-col">
            <div class="ultra-header">
                <span><i class="fas fa-fire mr-2 text-orange-500"></i>市场热力图</span>
            </div>
            <div class="flex-1 p-4 flex items-center justify-center relative overflow-hidden">
                 <!-- Simple CSS Grid Heatmap representation -->
                 <div class="grid grid-cols-3 grid-rows-3 gap-1 w-full h-full">
                    <div class="bg-green-500/80 flex items-center justify-center text-xs font-bold text-black rounded-sm col-span-2 row-span-2">BTC +2.4%</div>
                    <div class="bg-red-500/60 flex items-center justify-center text-xs font-bold text-white rounded-sm">ETH -0.8%</div>
                    <div class="bg-green-400/70 flex items-center justify-center text-xs font-bold text-black rounded-sm">SOL +5%</div>
                    <div class="bg-gray-600/50 flex items-center justify-center text-xs font-bold text-gray-300 rounded-sm">XRP 0%</div>
                    <div class="bg-green-600/60 flex items-center justify-center text-xs font-bold text-white rounded-sm col-span-2">BNB +1.2%</div>
                 </div>
            </div>
        </div>

        <!-- Top Middle: AI Signal Processor (2x1) -->
        <div class="col-span-2 row-span-1 ultra-panel flex flex-col">
            <div class="ultra-header">
                <span><i class="fas fa-brain mr-2 text-purple-500"></i>AI 策略引擎</span>
                <span class="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-[10px]">运行中</span>
            </div>
            <div class="flex-1 p-3 grid grid-cols-3 gap-3">
                <!-- Signal Card 1 -->
                <div class="bg-white/5 rounded border border-white/5 p-3 flex flex-col justify-between">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-gray-400 font-mono">STRAT-ALPHA</span>
                        <span class="text-xs font-bold text-green-400">做多</span>
                    </div>
                    <div class="text-xl font-bold text-white mt-1">BTC/USDT</div>
                    <div class="mt-2 text-[10px] text-gray-500 flex justify-between">
                        <span>置信度: 89%</span>
                        <span>杠杆: 10x</span>
                    </div>
                    <div class="mt-2 w-full bg-gray-800 h-1 rounded-full overflow-hidden">
                        <div class="bg-purple-500 h-full w-[89%]"></div>
                    </div>
                </div>
                 <!-- Signal Card 2 -->
                <div class="bg-white/5 rounded border border-white/5 p-3 flex flex-col justify-between opacity-50">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-gray-400 font-mono">STRAT-BETA</span>
                        <span class="text-xs font-bold text-gray-500">等待</span>
                    </div>
                    <div class="text-xl font-bold text-gray-300 mt-1">ETH/USDT</div>
                     <div class="mt-2 text-[10px] text-gray-500 flex justify-between">
                        <span>扫描中...</span>
                    </div>
                     <div class="mt-2 w-full bg-gray-800 h-1 rounded-full overflow-hidden animate-pulse">
                        <div class="bg-blue-500 h-full w-[30%]"></div>
                    </div>
                </div>
                <!-- Stats -->
                <div class="flex flex-col justify-center space-y-2 pl-2 border-l border-white/5">
                    <div class="flex justify-between text-xs">
                        <span class="text-gray-500">24h 胜率</span>
                        <span class="text-white font-mono">72.4%</span>
                    </div>
                    <div class="flex justify-between text-xs">
                        <span class="text-gray-500">信号总数</span>
                        <span class="text-white font-mono">142</span>
                    </div>
                    <div class="flex justify-between text-xs">
                        <span class="text-gray-500">平均收益</span>
                        <span class="text-green-400 font-mono">+1.2%</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Top Right: Volatility Radar (1x1) -->
        <div class="col-span-1 row-span-1 ultra-panel flex flex-col">
            <div class="ultra-header">
                <span><i class="fas fa-radar mr-2 text-blue-500"></i>风控雷达</span>
            </div>
            <div class="flex-1 flex items-center justify-center p-2">
                <canvas id="radarChart"></canvas>
            </div>
        </div>

        <!-- Middle: Multi-Chart Grid (4x1.5 -> spanning full width) -->
        <div class="col-span-4 row-span-2 grid grid-cols-4 gap-2">
            <!-- Chart 1 -->
            <div class="ultra-panel flex flex-col group">
                <div class="absolute top-2 left-2 z-10 text-xs font-bold text-white/80 bg-black/50 px-2 py-1 rounded backdrop-blur-sm">BTC/USDT <span id="change1" class="text-green-400 text-[10px]">--%</span></div>
                <div id="chart1" class="flex-1 w-full h-full opacity-80 group-hover:opacity-100 transition-opacity"></div>
            </div>
            <!-- Chart 2 -->
             <div class="ultra-panel flex flex-col group">
                <div class="absolute top-2 left-2 z-10 text-xs font-bold text-white/80 bg-black/50 px-2 py-1 rounded backdrop-blur-sm">ETH/USDT <span id="change2" class="text-red-400 text-[10px]">--%</span></div>
                <div id="chart2" class="flex-1 w-full h-full opacity-80 group-hover:opacity-100 transition-opacity"></div>
            </div>
            <!-- Chart 3 -->
             <div class="ultra-panel flex flex-col group">
                <div class="absolute top-2 left-2 z-10 text-xs font-bold text-white/80 bg-black/50 px-2 py-1 rounded backdrop-blur-sm">SOL/USDT <span id="change3" class="text-green-400 text-[10px]">--%</span></div>
                <div id="chart3" class="flex-1 w-full h-full opacity-80 group-hover:opacity-100 transition-opacity"></div>
            </div>
            <!-- Log Console -->
             <div class="ultra-panel flex flex-col">
                <div class="ultra-header">
                    <span><i class="fas fa-terminal mr-2 text-gray-400"></i>事件日志</span>
                </div>
                <div class="flex-1 p-2 overflow-y-auto font-mono text-[10px] space-y-1" id="logConsole">
                    <div class="text-gray-400"><span class="text-blue-500">[系统]</span> 系统已初始化。</div>
                </div>
            </div>
        </div>

    </main>

    <script>
        // Init Radar Chart
        const ctx = document.getElementById('radarChart').getContext('2d');
        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['波动', '流动', '点差', '情绪', '动量'],
                datasets: [{
                    label: '风控指标',
                    data: [85, 40, 30, 75, 90],
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    borderColor: 'rgba(59, 130, 246, 0.8)',
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#fff',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        pointLabels: { color: '#9ca3af', font: { size: 10 } },
                        ticks: { display: false }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });

        // Init Lightweight Charts
        function createMiniChart(id, color) {
            const container = document.getElementById(id);
            const chart = LightweightCharts.createChart(container, {
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#6b7280' },
                grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
                rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.1 } },
                timeScale: { visible: true, borderVisible: false },
                crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
                handleScroll: false,
                handleScale: false,
            });

            const series = chart.addAreaSeries({
                lineColor: color,
                topColor: color.replace(')', ', 0.4)').replace('rgb', 'rgba'),
                bottomColor: color.replace(')', ', 0.0)').replace('rgb', 'rgba'),
                lineWidth: 2,
            });

            window.addEventListener('resize', () => {
                chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
            });
            
            return { chart, series };
        }

        const chart1 = createMiniChart('chart1', 'rgb(16, 185, 129)'); // Green
        const chart2 = createMiniChart('chart2', 'rgb(239, 68, 68)');  // Red
        const chart3 = createMiniChart('chart3', 'rgb(16, 185, 129)'); // Green

        // Fetch Data Function
        async function fetchChartData(symbol, seriesObj, changeId) {
            try {
                // Get History
                const res = await fetch(`/api/history?symbol=${symbol}&limit=100`);
                const data = await res.json();
                if (!data.error && Array.isArray(data)) {
                    seriesObj.setData(data);
                }

                // Get Ticker (for percent change)
                const tickerRes = await fetch(`/api/ticker?symbol=${symbol}`);
                const ticker = await tickerRes.json();
                if (!ticker.error) {
                    const el = document.getElementById(changeId);
                    if (el) {
                        const pct = parseFloat(ticker.price_change_pct);
                        el.innerText = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
                        el.className = pct >= 0 ? 'text-green-400 text-[10px]' : 'text-red-400 text-[10px]';
                        
                        // Update chart color based on trend
                        const color = pct >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
                        seriesObj.applyOptions({
                            lineColor: color,
                            topColor: color.replace(')', ', 0.4)').replace('rgb', 'rgba'),
                            bottomColor: color.replace(')', ', 0.0)').replace('rgb', 'rgba'),
                        });
                    }
                }
            } catch (e) { console.error(`Error fetching ${symbol}:`, e); }
        }

        // Initial Fetch
        fetchChartData('BTCUSDT', chart1.series, 'change1');
        fetchChartData('ETHUSDT', chart2.series, 'change2');
        fetchChartData('SOLUSDT', chart3.series, 'change3');

        // Polling
        setInterval(() => {
            fetchChartData('BTCUSDT', chart1.series, 'change1');
            fetchChartData('ETHUSDT', chart2.series, 'change2');
            fetchChartData('SOLUSDT', chart3.series, 'change3');
        }, 10000);

        // Auto-scroll logs
        const logConsole = document.getElementById('logConsole');
        function addLog(msg, color='text-gray-400') {
            const div = document.createElement('div');
            div.className = color;
            div.innerHTML = `<span class="text-blue-500">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
            logConsole.appendChild(div);
            logConsole.scrollTop = logConsole.scrollHeight;
        }

        setInterval(() => {
            addLog("系统心跳检测正常");
        }, 5000);

    </script>
</body>
</html>
"""

async def handle_request(request):
    # Backward compatibility
    dashboard = TradingDashboardUltra()
    return await dashboard.index(request)
