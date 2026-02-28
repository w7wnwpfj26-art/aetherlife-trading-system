"""
合约交易系统主程序
整合数据层、策略层、执行层、风控层
"""

import asyncio
import copy
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

# 导入各模块
from data.data_fetcher import BinanceDataFetcher, OKXDataFetcher, create_data_fetcher
from strategies import (
    BreakoutStrategy, GridStrategy, MACrossStrategy,
    RSIStrategy, VolumeStrategy, create_strategy
)
from execution.exchange_client import BinanceClient, OKXClient, create_client
from utils.risk_manager import RiskManager, PositionManager
from utils.config import validate_config
from utils.logger import get_logger

logger = get_logger()


class TradingBot:
    """合约交易机器人"""
    
    def __init__(self, config: dict):
        self.config = copy.deepcopy(config)
        self.running = False
        
        # 交易所
        self.exchange = config.get("exchange", "binance")
        self.testnet = config.get("testnet", True)
        
        # API
        self.api_key = config.get("api_key", os.getenv("BINANCE_API_KEY", ""))
        self.secret_key = config.get("secret_key", os.getenv("BINANCE_SECRET_KEY", ""))
        
        # 数据获取
        self.data_fetcher = None
        self.client = None
        
        # 策略
        self.strategy_name = config.get("strategy", "breakout")
        self.strategy = None
        
        # 风控
        self.risk_manager = RiskManager(config.get("risk", {}))
        self.position_manager = PositionManager()
        
        # 交易对
        self.symbols = config.get("symbols", ["BTCUSDT"])
        self.current_symbol = self.symbols[0]
        self.timeframe = config.get("timeframe", "1m")
        
        # 状态
        self.last_signal = 0
        self.last_price = 0
        # 追踪止损：记录每个标的持仓期间的最高/最低价
        self._peak_prices: dict = {}
        
    async def initialize(self):
        """初始化"""
        errs = validate_config(self.config)
        if errs:
            for e in errs:
                logger.error(e)
            raise ValueError("配置校验失败: " + "; ".join(errs))
        logger.info("=" * 60)
        logger.info("🚀 合约交易系统初始化")
        logger.info("=" * 60)
        self.data_fetcher = create_data_fetcher(self.exchange, self.testnet)
        
        # 初始化交易客户端
        self.client = create_client(
            self.exchange, 
            self.api_key, 
            self.secret_key, 
            self.testnet
        )
        
        # 初始化策略
        strategy_config = self.config.get("strategy_config", {})
        self.strategy = create_strategy(self.strategy_name, strategy_config)
        
        logger.info(f"✓ 交易所: {self.exchange} (测试网: {self.testnet})")
        logger.info(f"✓ 策略: {self.strategy.name}")
        logger.info(f"✓ 交易对: {', '.join(self.symbols)}")
        logger.info(f"✓ 时间周期: {self.timeframe}")

    async def fetch_market_data(self) -> Dict:
        """获取市场数据（OHLCV 与 Ticker 并行请求）"""
        symbol, tf = self.current_symbol, self.timeframe
        df, ticker = await asyncio.gather(
            self.data_fetcher.get_ohlcv(symbol, tf, 100),
            self.data_fetcher.get_ticker(symbol),
        )
        return {"df": df, "ticker": ticker}

    async def analyze(self, data: Dict) -> int:
        """分析市场，生成信号"""
        df = data.get("df")
        if df is None or not hasattr(df, "iloc") or len(df) < 2:
            return 0
        df = self.strategy.generate_signals(df)
        if "signal" not in df.columns or df["signal"].empty:
            return 0
        signal = int(df["signal"].iloc[-1])
        if signal != self.last_signal:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 信号变化: {self.last_signal} → {signal}")
            self.last_signal = signal
        return signal
    
    async def execute_signal(self, signal: int):
        """执行信号"""
        if signal == 0:
            return
        
        # 检查是否可以交易
        can_trade = self.risk_manager.can_trade()
        if can_trade.get("should_stop"):
            logger.warning("风控限制: %s", can_trade.get("reason"))
            return
        
        # 获取当前价格
        price = await self.client.get_price(self.current_symbol)
        self.last_price = price
        
        # 获取账户余额
        balance = await self.client.get_balance()
        balance_amount = balance.get("total", 10000)  # 默认10000
        
        signal_info = {"strength": 0.8}
        quantity = self.risk_manager.calculate_position_size(
            signal_info, balance_amount, price
        )
        # 交易所最小精度：常见为 3 位小数，避免 -402 等错误
        quantity = round(quantity, 3)
        if quantity <= 0:
            logger.warning("计算仓位为 0 或负数，跳过下单")
            return
        if signal == 1 and not self.position_manager.has_position(self.current_symbol):
            logger.info(f"📈 买入开多: {self.current_symbol} @ {price}, 数量: {quantity}")
            try:
                result = await self.client.place_order(
                    symbol=self.current_symbol,
                    side="BUY",
                    order_type="MARKET",
                    quantity=quantity,
                    leverage=self.config.get("leverage", 10)
                )
            except Exception:
                logger.exception("开多下单失败")
                return
            if result.get("success"):
                self.position_manager.open_position(
                    self.current_symbol, "LONG", quantity, price,
                    self.config.get("leverage", 10)
                )
                logger.info(f"✓ 开多成功: {result.get('order_id')}")
        elif signal == -1 and not self.position_manager.has_position(self.current_symbol):
            logger.info(f"📉 卖出开空: {self.current_symbol} @ {price}, 数量: {quantity}")
            try:
                result = await self.client.place_order(
                    symbol=self.current_symbol,
                    side="SELL",
                    order_type="MARKET",
                    quantity=quantity,
                    leverage=self.config.get("leverage", 10)
                )
            except Exception:
                logger.exception("开空下单失败")
                return
            if result.get("success"):
                self.position_manager.open_position(
                    self.current_symbol, "SHORT", quantity, price,
                    self.config.get("leverage", 10)
                )
                logger.info(f"✓ 开空成功: {result.get('order_id')}")
        elif signal == -1 and self.position_manager.has_position(self.current_symbol):
            pos = self.position_manager.get_position(self.current_symbol)
            logger.info(f"🔄 平仓: {self.current_symbol} @ {price}")
            side = "SELL" if pos["side"] == "LONG" else "BUY"
            try:
                result = await self.client.place_order(
                    symbol=self.current_symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=pos["quantity"],
                    reduce_only=True
                )
            except Exception:
                logger.exception("平仓下单失败")
                return
            if result.get("success"):
                close_result = self.position_manager.close_position(self.current_symbol, price)
                logger.info(f"✓ 平仓成功, 盈亏: {close_result.get('pnl', 0):.2f} USDT")
                self.risk_manager.record_trade({
                    "pnl": close_result.get("pnl", 0),
                    "balance": balance_amount,
                    "symbol": self.current_symbol,
                    "side": pos["side"]
                })
    
    async def check_positions(self):
        """检查仓位状态，止损 / 止盈 / 追踪止损"""
        if not self.position_manager.has_position(self.current_symbol):
            # 无持仓时清理峰值记录
            self._peak_prices.pop(self.current_symbol, None)
            return

        pos = self.position_manager.get_position(self.current_symbol)

        # 获取当前价格
        price = await self.client.get_price(self.current_symbol)
        self.position_manager.update_position(self.current_symbol, price)

        # 维护追踪止损所需的峰值价格
        sym = self.current_symbol
        if pos["side"].upper() == "LONG":
            self._peak_prices[sym] = max(self._peak_prices.get(sym, price), price)
        else:
            self._peak_prices[sym] = min(self._peak_prices.get(sym, price), price)
        peak_price = self._peak_prices[sym]

        # 检查止损
        sl_check = self.risk_manager.check_stop_loss(
            pos["entry_price"], price, pos["side"]
        )
        # 检查止盈
        tp_check = self.risk_manager.check_take_profit(
            pos["entry_price"], price, pos["side"]
        )
        # 检查追踪止损
        ts_check = self.risk_manager.check_trailing_stop(
            pos["entry_price"], price, pos["side"], peak_price
        )

        # 任一条件触发即平仓
        should_close = (
            sl_check.get("should_stop")
            or tp_check.get("should_stop")
            or ts_check.get("should_stop")
        )

        if should_close:
            reason = sl_check.get("reason") or tp_check.get("reason") or ts_check.get("reason")
            logger.warning("触发%s, 平仓: %s @ %s", reason, self.current_symbol, price)
            side = "SELL" if pos["side"] == "LONG" else "BUY"
            try:
                await self.client.place_order(
                    symbol=self.current_symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=pos["quantity"],
                    reduce_only=True
                )
            except Exception:
                logger.exception("止损/止盈平仓下单失败")
                return
            close_result = self.position_manager.close_position(self.current_symbol, price)
            self._peak_prices.pop(self.current_symbol, None)
            logger.info("✓ 平仓完成, 盈亏: %.2f USDT", close_result.get("pnl", 0))
            # 止损/止盈平仓也计入风控统计
            balance = (await self.client.get_balance()).get("total", 0) or 10000
            self.risk_manager.record_trade({
                "pnl": close_result.get("pnl", 0),
                "balance": balance,
                "symbol": self.current_symbol,
                "side": pos["side"],
            })
    
    async def run(self):
        """运行交易机器人"""
        await self.initialize()
        
        self.running = True
        loop_interval = self.config.get("loop_interval", 5)  # 默认5秒

        logger.info("🎯 开始交易，共 %d 个标的", len(self.symbols))
        while self.running:
            # 多标的轮询：依次处理每个交易对
            for symbol in self.symbols:
                if not self.running:
                    break
                self.current_symbol = symbol
                try:
                    data = await self.fetch_market_data()
                    signal = await self.analyze(data)
                    await self.check_positions()
                    await self.execute_signal(signal)
                    ticker = data.get("ticker") or {}
                    logger.info(
                        "%s %s: %s | 信号: %s | 涨跌: %s%%",
                        datetime.now().strftime("%H:%M:%S"),
                        self.current_symbol,
                        ticker.get("last_price"),
                        signal,
                        ticker.get("price_change_pct", 0),
                    )
                except Exception:
                    logger.exception("处理 %s 时异常", symbol)
            await asyncio.sleep(loop_interval)

    async def stop(self):
        """停止交易机器人"""
        self.running = False
        logger.info("🛑 交易系统已停止")
        if self.data_fetcher:
            await self.data_fetcher.close()
        if self.client:
            await self.client.close()
        stats = self.risk_manager.get_stats()
        logger.info("📊 交易统计: 总次数=%s 日次数=%s 盈/亏=%s/%s 日盈亏=%.2f USDT",
                   stats["total_trades"], stats["daily"]["trade_count"],
                   stats["daily"]["win_count"], stats["daily"]["loss_count"],
                   stats["daily"]["pnl"])


# 配置
DEFAULT_CONFIG = {
    "exchange": "binance",
    "testnet": True,
    "strategy": "breakout",
    "symbols": ["BTCUSDT"],
    "timeframe": "1m",
    "leverage": 10,
    "loop_interval": 5,
    "risk": {
        "max_position_pct": 0.1,  # 最大10%仓位
        "stop_loss_pct": 0.02,    # 2%止损
        "take_profit_pct": 0.05, # 5%止盈
        "max_daily_trades": 20,
        "max_consecutive_losses": 5,
        "circuit_breaker_loss_pct": 0.2
    },
    "strategy_config": {
        "lookback_period": 20,
        "threshold": 0.005
    }
}


async def main():
    """主函数"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from utils.config import deep_merge
    config = copy.deepcopy(DEFAULT_CONFIG)
    for config_file in ("config.json", os.path.join(os.path.dirname(__file__), "..", "config.json")):
        if os.path.isfile(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = deep_merge(config, json.load(f))
            break
    bot = TradingBot(config)
    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
