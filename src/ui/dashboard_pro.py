
import logging
import json
import asyncio
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingDashboardPro:
    """Pro 交易终端 Web UI"""

    def __init__(self, data_fetcher=None):
        self.data_fetcher = data_fetcher
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/history', self.api_history)
        self.app.router.add_get('/api/ticker', self.api_ticker)
        self.app.router.add_get('/api/orderbook', self.api_orderbook)

    async def index(self, request):
        """主页"""
        return web.Response(text=self.get_html(), content_type='text/html')

    async def api_history(self, request):
        """获取K线历史数据"""
        symbol = request.query.get('symbol', 'BTCUSDT')
        timeframe = request.query.get('timeframe', '15m')
        limit = int(request.query.get('limit', 1000))
        
        if not self.data_fetcher:
            return web.json_response({'error': 'Data fetcher not available'}, status=500)
            
        try:
            df = await self.data_fetcher.get_ohlcv(symbol, timeframe, limit)
            # 转换 DataFrame 为 Lightweight Charts 格式
            data = []
            for _, row in df.iterrows():
                data.append({
                    'time': int(row['open_time'].timestamp()),
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                })
            return web.json_response(data)
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
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

    async def api_orderbook(self, request):
        """获取订单簿"""
        symbol = request.query.get('symbol', 'BTCUSDT')
        if not self.data_fetcher:
             return web.json_response({'error': 'Data fetcher not available'}, status=500)
        try:
            book = await self.data_fetcher.get_orderbook(symbol, limit=20)
            return web.json_response(book)
        except Exception as e:
             return web.json_response({'error': str(e)}, status=500)

    def get_html(self):
        return """
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pro 交易终端 | 量化交易系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@300;400;500;600&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: #050505;
            color: #e5e7eb;
        }
        
        .font-mono {
            font-family: 'JetBrains Mono', monospace;
        }

        .glass-panel {
            background: rgba(20, 20, 25, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }

        .glass-header {
            background: rgba(20, 20, 25, 0.8);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.02);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.25);
        }

        .text-up { color: #10b981; }
        .text-down { color: #ef4444; }
        .bg-up-soft { background-color: rgba(16, 185, 129, 0.15); }
        .bg-down-soft { background-color: rgba(239, 68, 68, 0.15); }
        
        .order-book-row:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        .tab-active {
            color: #60a5fa;
            border-bottom: 2px solid #60a5fa;
        }
        
        .tab-inactive {
            color: #9ca3af;
            border-bottom: 2px solid transparent;
        }
        .tab-inactive:hover {
            color: #d1d5db;
        }
    </style>
</head>
<body class="h-screen flex flex-col overflow-hidden selection:bg-blue-500/30">

    <!-- Top Navigation -->
    <nav class="h-12 glass-header flex items-center justify-between px-4 z-50 shrink-0">
        <div class="flex items-center space-x-6">
            <div class="flex items-center space-x-2">
                <div class="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></div>
                <span class="font-bold text-lg tracking-tight text-white">专业版<span class="text-blue-500 font-light">终端</span></span>
            </div>
            
            <div class="hidden md:flex items-center space-x-1 bg-white/5 rounded-lg p-1" id="marketSelector">
                <button onclick="changeSymbol('BTCUSDT')" class="px-3 py-1 text-xs font-medium rounded hover:bg-white/5 text-gray-400" data-symbol="BTCUSDT">BTC/USDT</button>
                <button onclick="changeSymbol('ETHUSDT')" class="px-3 py-1 text-xs font-medium rounded hover:bg-white/5 text-gray-400" data-symbol="ETHUSDT">ETH/USDT</button>
                <button onclick="changeSymbol('SOLUSDT')" class="px-3 py-1 text-xs font-medium rounded hover:bg-white/5 text-gray-400" data-symbol="SOLUSDT">SOL/USDT</button>
            </div>
        </div>

        <div class="flex items-center space-x-4">
            <div class="flex items-center space-x-3 text-xs font-mono">
                <div class="flex flex-col items-end">
                    <span class="text-gray-400">最新价</span>
                    <span class="text-up text-sm font-bold" id="headerPrice">--</span>
                </div>
                <div class="h-6 w-px bg-white/10"></div>
                <div class="flex flex-col items-end">
                    <span class="text-gray-400">24h 涨跌</span>
                    <span class="text-up font-medium" id="headerChange">--</span>
                </div>
                <div class="h-6 w-px bg-white/10"></div>
                <div class="flex flex-col items-end">
                    <span class="text-gray-400">24h 成交量</span>
                    <span class="text-white font-medium" id="headerVolume">--</span>
                </div>
            </div>
            
            <div class="h-6 w-px bg-white/10 mx-2"></div>
            
            <div class="flex items-center space-x-2">
                <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-xs font-bold border border-white/10 shadow-lg">
                    AI
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Layout Grid -->
    <div class="flex-1 grid grid-cols-12 grid-rows-6 gap-1 p-1 overflow-hidden">
        
        <!-- Left Sidebar: Market List (2 cols, 4 rows) -->
        <div class="col-span-2 row-span-4 glass-panel rounded-lg flex flex-col overflow-hidden">
            <div class="flex items-center justify-between p-2 border-b border-white/5">
                <span class="text-xs font-semibold text-gray-300">市场列表</span>
                <i class="fas fa-search text-gray-500 text-xs"></i>
            </div>
            <div class="flex-1 overflow-y-auto">
                <table class="w-full text-left text-xs">
                    <thead class="text-gray-500 bg-white/5 sticky top-0">
                        <tr>
                            <th class="p-2 font-medium">币种</th>
                            <th class="p-2 font-medium text-right">价格</th>
                            <th class="p-2 font-medium text-right">涨跌</th>
                        </tr>
                    </thead>
                    <tbody class="font-mono" id="marketList">
                        <!-- Filled by JS -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Center: Chart (7 cols, 4 rows) -->
        <div class="col-span-7 row-span-4 glass-panel rounded-lg flex flex-col relative group">
            <div class="absolute top-2 left-2 z-10 flex space-x-1">
                <button onclick="changeTimeframe('1m')" class="px-2 py-1 text-[10px] font-medium bg-white/10 hover:bg-white/20 rounded text-gray-300">1m</button>
                <button onclick="changeTimeframe('5m')" class="px-2 py-1 text-[10px] font-medium bg-white/10 hover:bg-white/20 rounded text-gray-300">5m</button>
                <button onclick="changeTimeframe('15m')" class="px-2 py-1 text-[10px] font-medium bg-blue-600 text-white rounded shadow-sm">15m</button>
                <button onclick="changeTimeframe('1h')" class="px-2 py-1 text-[10px] font-medium bg-white/10 hover:bg-white/20 rounded text-gray-300">1h</button>
                <button onclick="changeTimeframe('4h')" class="px-2 py-1 text-[10px] font-medium bg-white/10 hover:bg-white/20 rounded text-gray-300">4h</button>
                <div class="w-px h-4 bg-white/10 mx-1"></div>
                <button onclick="toggleIndicators()" class="px-2 py-1 text-[10px] font-medium bg-white/10 hover:bg-white/20 rounded text-gray-300" title="切换指标 (MA)"><i class="fas fa-chart-line"></i></button>
            </div>
            <div id="mainChart" class="flex-1 w-full h-full"></div>
            <div id="chartLoading" class="absolute inset-0 flex items-center justify-center bg-black/50 z-20 hidden">
                <i class="fas fa-spinner fa-spin text-2xl text-blue-500"></i>
            </div>
        </div>

        <!-- Right: Order Book & Trades (3 cols, 4 rows) -->
        <div class="col-span-3 row-span-4 glass-panel rounded-lg flex flex-col overflow-hidden">
            <div class="flex border-b border-white/5">
                <button class="flex-1 py-2 text-xs font-medium text-center tab-active">订单簿</button>
                <button class="flex-1 py-2 text-xs font-medium text-center tab-inactive">最新成交</button>
            </div>
            
            <!-- Order Book Content -->
            <div class="flex-1 flex flex-col overflow-hidden font-mono text-[10px] relative">
                <!-- Asks -->
                <div class="flex-1 overflow-hidden flex flex-col-reverse" id="orderBookAsks">
                    <div class="flex px-2 py-0.5 text-gray-500">
                        <span class="w-1/3">价格</span>
                        <span class="w-1/3 text-right">数量</span>
                        <span class="w-1/3 text-right">总额</span>
                    </div>
                </div>
                
                <!-- Spread -->
                <div class="py-1 px-2 border-y border-white/5 flex justify-between items-center bg-white/[0.02]">
                    <span class="text-up text-lg font-bold" id="obCurrentPrice">--</span>
                    <span class="text-gray-500 text-[10px]" id="obSpread">--</span>
                </div>
                
                <!-- Bids -->
                <div class="flex-1 overflow-hidden" id="orderBookBids">
                </div>
            </div>
            
            <!-- Quick Trade Panel -->
            <div class="p-2 border-t border-white/5 bg-white/[0.02]">
                <div class="flex space-x-2 mb-2">
                    <button class="flex-1 py-1.5 bg-up-soft text-up rounded hover:bg-green-500/20 text-xs font-bold transition-colors">买入</button>
                    <button class="flex-1 py-1.5 bg-down-soft text-down rounded hover:bg-red-500/20 text-xs font-bold transition-colors">卖出</button>
                </div>
                <div class="flex items-center space-x-2">
                    <input type="text" value="0.01" class="w-full bg-black/20 border border-white/10 rounded px-2 py-1 text-xs text-right font-mono focus:border-blue-500 outline-none transition-colors">
                    <span class="text-[10px] text-gray-500">BTC</span>
                </div>
            </div>
        </div>

        <!-- Bottom: Positions & Orders (9 cols, 2 rows) -->
        <div class="col-span-9 row-span-2 glass-panel rounded-lg flex flex-col overflow-hidden">
            <div class="flex border-b border-white/5 bg-white/[0.02]">
                <button class="px-4 py-2 text-xs font-medium tab-active">当前持仓 (0)</button>
                <button class="px-4 py-2 text-xs font-medium tab-inactive">当前委托 (0)</button>
                <button class="px-4 py-2 text-xs font-medium tab-inactive">历史委托</button>
                <button class="px-4 py-2 text-xs font-medium tab-inactive">已实现盈亏</button>
            </div>
            <div class="flex-1 overflow-auto">
                <table class="w-full text-left text-xs">
                    <thead class="text-gray-500 border-b border-white/5">
                        <tr>
                            <th class="p-3 font-medium">币种</th>
                            <th class="p-3 font-medium">方向</th>
                            <th class="p-3 font-medium text-right">持仓量</th>
                            <th class="p-3 font-medium text-right">开仓价</th>
                            <th class="p-3 font-medium text-right">标记价</th>
                            <th class="p-3 font-medium text-right">强平价</th>
                            <th class="p-3 font-medium text-right">保证金</th>
                            <th class="p-3 font-medium text-right">盈亏 (收益率)</th>
                            <th class="p-3 font-medium text-right">操作</th>
                        </tr>
                    </thead>
                    <tbody class="font-mono" id="positionList">
                        <tr>
                            <td colspan="9" class="p-4 text-center text-gray-500">暂无持仓</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Bottom Right: Account/Logs (3 cols, 2 rows) -->
        <div class="col-span-3 row-span-2 glass-panel rounded-lg flex flex-col">
            <div class="p-3 border-b border-white/5 flex justify-between items-center">
                <span class="text-xs font-semibold text-gray-300">资产账户</span>
                <i class="fas fa-wallet text-gray-500 text-xs"></i>
            </div>
            <div class="p-4 space-y-4">
                <div>
                    <div class="text-gray-500 text-xs mb-1">总资产估值 (USDT)</div>
                    <div class="text-2xl font-mono font-bold text-white tracking-tight">10,000.00</div>
                    <div class="text-xs text-up mt-1">+$0.00 今日</div>
                </div>
                
                <div class="space-y-2">
                    <div class="flex justify-between text-xs">
                        <span class="text-gray-400">可用余额</span>
                        <span class="text-white font-mono">10,000.00</span>
                    </div>
                    <div class="w-full bg-white/5 rounded-full h-1.5">
                        <div class="bg-blue-500 h-1.5 rounded-full" style="width: 100%"></div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-2 mt-2">
                    <button class="py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium transition-colors">充值</button>
                    <button class="py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 rounded text-xs font-medium border border-white/10 transition-colors">划转</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // State
        let currentSymbol = 'BTCUSDT';
        let currentTimeframe = '15m';
        let chart, candleSeries, ma7Series, ma25Series;
        let showIndicators = true;

        // Initialize Chart
        function initChart() {
            const chartContainer = document.getElementById('mainChart');
            chart = LightweightCharts.createChart(chartContainer, {
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#9ca3af',
                },
                grid: {
                    vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                    horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                },
                timeScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    timeVisible: true,
                },
            });

            candleSeries = chart.addCandlestickSeries({
                upColor: '#10b981',
                downColor: '#ef4444',
                borderVisible: false,
                wickUpColor: '#10b981',
                wickDownColor: '#ef4444',
            });
            
            // Add MA Lines
            ma7Series = chart.addLineSeries({ color: '#3b82f6', lineWidth: 1, title: 'MA7' });
            ma25Series = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, title: 'MA25' });

            // Auto-resize
            window.addEventListener('resize', () => {
                chart.applyOptions({ width: chartContainer.clientWidth, height: chartContainer.clientHeight });
            });
        }

        // Fetch Data
        async function fetchHistory() {
            document.getElementById('chartLoading').classList.remove('hidden');
            try {
                const res = await fetch(`/api/history?symbol=${currentSymbol}&timeframe=${currentTimeframe}&limit=1000`);
                const data = await res.json();
                
                if (data.error) throw new Error(data.error);
                
                candleSeries.setData(data);
                
                // Calculate and set MA data
                if (showIndicators) {
                    const ma7 = calculateSMA(data, 7);
                    const ma25 = calculateSMA(data, 25);
                    ma7Series.setData(ma7);
                    ma25Series.setData(ma25);
                }
                
                // Update header
                if (data.length > 0) {
                    const last = data[data.length - 1];
                    updateHeader(last.close);
                }

            } catch (e) {
                console.error("Fetch history error:", e);
            } finally {
                document.getElementById('chartLoading').classList.add('hidden');
            }
        }

        function calculateSMA(data, period) {
            const sma = [];
            for (let i = period - 1; i < data.length; i++) {
                let sum = 0;
                for (let j = 0; j < period; j++) {
                    sum += data[i - j].close;
                }
                sma.push({ time: data[i].time, value: sum / period });
            }
            return sma;
        }

        async function fetchTicker() {
            try {
                const res = await fetch(`/api/ticker?symbol=${currentSymbol}`);
                const data = await res.json();
                if (!data.error) {
                    updateHeader(data.last_price, data.price_change_pct, data.volume);
                }
            } catch (e) { console.error(e); }
        }
        
        async function fetchOrderBook() {
            try {
                const res = await fetch(`/api/orderbook?symbol=${currentSymbol}`);
                const data = await res.json();
                if (!data.error) {
                    renderOrderBook(data);
                }
            } catch (e) { console.error(e); }
        }

        function renderOrderBook(data) {
            const asksContainer = document.getElementById('orderBookAsks');
            const bidsContainer = document.getElementById('orderBookBids');
            
            // Render Asks (Reverse order for display)
            let asksHtml = '';
            const maxVol = Math.max(...data.asks.map(a => a[1]), ...data.bids.map(b => b[1]));
            
            data.asks.slice(0, 15).reverse().forEach(ask => {
                const price = ask[0];
                const qty = ask[1];
                const percent = (qty / maxVol) * 100;
                asksHtml += `
                    <div class="flex px-2 py-0.5 order-book-row relative">
                        <div class="absolute right-0 top-0 bottom-0 bg-red-500/10 transition-all duration-300" style="width: ${percent}%"></div>
                        <span class="w-1/3 text-down relative z-10">${price.toFixed(2)}</span>
                        <span class="w-1/3 text-right text-gray-300 relative z-10">${qty.toFixed(3)}</span>
                        <span class="w-1/3 text-right text-gray-400 relative z-10">--</span>
                    </div>
                `;
            });
            asksContainer.innerHTML = `
                <div class="flex px-2 py-0.5 text-gray-500 text-[10px]">
                    <span class="w-1/3">价格</span>
                    <span class="w-1/3 text-right">数量</span>
                    <span class="w-1/3 text-right">总额</span>
                </div>
                ${asksHtml}
            `;
            
            // Render Bids
            let bidsHtml = '';
            data.bids.slice(0, 15).forEach(bid => {
                const price = bid[0];
                const qty = bid[1];
                const percent = (qty / maxVol) * 100;
                bidsHtml += `
                    <div class="flex px-2 py-0.5 order-book-row relative">
                        <div class="absolute right-0 top-0 bottom-0 bg-green-500/10 transition-all duration-300" style="width: ${percent}%"></div>
                        <span class="w-1/3 text-up relative z-10">${price.toFixed(2)}</span>
                        <span class="w-1/3 text-right text-gray-300 relative z-10">${qty.toFixed(3)}</span>
                        <span class="w-1/3 text-right text-gray-400 relative z-10">--</span>
                    </div>
                `;
            });
            bidsContainer.innerHTML = bidsHtml;
        }

        function updateHeader(price, change, volume) {
            if (price) {
                const el = document.getElementById('headerPrice');
                el.innerText = parseFloat(price).toLocaleString(undefined, {minimumFractionDigits: 2});
                document.getElementById('obCurrentPrice').innerText = parseFloat(price).toLocaleString(undefined, {minimumFractionDigits: 2});
            }
            if (change !== undefined) {
                const el = document.getElementById('headerChange');
                el.innerText = (change > 0 ? '+' : '') + parseFloat(change).toFixed(2) + '%';
                el.className = change >= 0 ? 'text-up font-medium' : 'text-down font-medium';
            }
            if (volume !== undefined) {
                document.getElementById('headerVolume').innerText = (parseFloat(volume) / 1000000).toFixed(2) + 'M';
            }
        }

        // Actions
        window.changeSymbol = (symbol) => {
            currentSymbol = symbol;
            // Update UI buttons
            document.querySelectorAll('#marketSelector button').forEach(btn => {
                if (btn.dataset.symbol === symbol) {
                    btn.classList.remove('text-gray-400', 'hover:bg-white/5');
                    btn.classList.add('bg-blue-600/20', 'text-blue-400');
                } else {
                    btn.classList.add('text-gray-400', 'hover:bg-white/5');
                    btn.classList.remove('bg-blue-600/20', 'text-blue-400');
                }
            });
            fetchHistory();
            fetchTicker();
            fetchOrderBook();
        };

        window.changeTimeframe = (tf) => {
            currentTimeframe = tf;
            fetchHistory();
        };

        window.toggleIndicators = () => {
            showIndicators = !showIndicators;
            if (showIndicators) {
                fetchHistory(); // Recalculate and show
            } else {
                ma7Series.setData([]);
                ma25Series.setData([]);
            }
        };

        // Init
        initChart();
        fetchHistory();
        fetchTicker();
        fetchOrderBook();
        
        // Polling
        setInterval(fetchTicker, 5000);
        setInterval(fetchOrderBook, 5000);
        setInterval(() => {
            // Update last candle (simplified)
            // In a real app, use WebSocket for live candle updates
            fetchHistory(); 
        }, 15000);

    </script>
</body>
</html>
"""

async def handle_request(request):
    # Backward compatibility wrapper if needed, but we should use the class
    dashboard = TradingDashboardPro() 
    return await dashboard.index(request)
