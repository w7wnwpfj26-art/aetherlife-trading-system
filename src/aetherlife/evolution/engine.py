"""
进化引擎：反思昨日 → 生成 N 个变体 → 回测 → 选优
Phase 0：参数变体 + 简单回测；Phase 1+：LLM 生成代码 + Genetic/RL
"""

import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from ..memory.store import MemoryStore

logger = logging.getLogger("aetherlife.evolution")


class EvolutionEngine:
    """自我进化：每日触发，产出新策略/参数"""

    def __init__(
        self,
        memory: MemoryStore,
        symbol: str = "BTCUSDT",
        exchange: str = "binance",
        testnet: bool = True,
        variants_per_round: int = 10,
        min_sharpe_to_deploy: float = 0.5,
        allow_code_gen: bool = False,
    ):
        self.memory = memory
        self.symbol = symbol
        self.exchange = exchange
        self.testnet = testnet
        self.variants_per_round = variants_per_round
        self.min_sharpe_to_deploy = min_sharpe_to_deploy
        self.allow_code_gen = allow_code_gen
        self._fetcher = None

    async def _get_fetcher(self):
        if self._fetcher is None:
            from data.data_fetcher import create_data_fetcher
            self._fetcher = create_data_fetcher(self.exchange, self.testnet)
        return self._fetcher

    async def run_daily_evolution(self) -> dict:
        """执行一轮每日进化（可被 cron/调度在凌晨调用）"""
        logger.info("AetherLife 进化轮次开始")
        recent = self.memory.get_recent_trades(n=200)
        recent_dec = self.memory.get_recent_decisions(n=100)
        daily_pnl = self.memory.get_daily_pnl()
        reflection = self._reflect(recent, recent_dec, daily_pnl)
        logger.info("反思摘要: %s", reflection[:500] if len(reflection) > 500 else reflection)
        variants = await self._generate_variants(reflection)
        results = await self._backtest_variants(variants)
        best = self._select_best(results)
        if best and best.get("sharpe", 0) >= self.min_sharpe_to_deploy:
            logger.info("进化轮次选出胜者: %s", best)
        else:
            logger.info("本轮无达标胜者，保持当前策略")
        return {"reflection": reflection, "variants": len(variants), "best": best, "results": results}

    def _reflect(self, trades: list, decisions: list, daily_pnl: float) -> str:
        """生成反思文本（供 LLM 或规则用）"""
        lines = [
            f"昨日 PnL: {daily_pnl:.2f}",
            f"交易笔数: {len(trades)}",
            f"决策记录数: {len(decisions)}",
        ]
        return "\n".join(lines)

    async def _generate_variants(self, reflection: str) -> List[dict]:
        """生成策略参数变体（突破/RSI 等不同参数）"""
        variants = []
        # 突破策略变体
        for lookback in [15, 20, 25]:
            for thresh in [0.003, 0.005, 0.008]:
                variants.append({
                    "strategy_type": "breakout",
                    "config": {"lookback_period": lookback, "threshold": thresh},
                })
        # RSI 变体
        for oversold in [25, 30, 35]:
            for overbought in [65, 70, 75]:
                variants.append({
                    "strategy_type": "rsi",
                    "config": {"oversold": oversold, "overbought": overbought},
                })
        return variants[: self.variants_per_round]

    async def _backtest_variants(self, variants: List[dict]) -> List[dict]:
        """用历史 K 线回测各变体，返回 sharpe / total_return"""
        if not variants:
            return []
        fetcher = await self._get_fetcher()
        try:
            df = await fetcher.get_ohlcv(self.symbol, "1h", 500)
        except Exception as e:
            logger.warning("进化回测拉取数据失败: %s", e)
            return []
        if df is None or len(df) < 100:
            return []
        results = []
        for v in variants:
            try:
                st_type = v.get("strategy_type", "breakout")
                config = v.get("config", {})
                from strategies.factory import create_strategy
                strategy = create_strategy(st_type, config)
                sig_df = strategy.generate_signals(df)
                if sig_df is None or "signal" not in sig_df.columns:
                    continue
                ret, sharpe = self._simple_backtest(sig_df)
                results.append({
                    "variant": v,
                    "total_return": ret,
                    "sharpe": sharpe,
                })
            except Exception as e:
                logger.debug("变体回测失败 %s: %s", v, e)
        return results

    def _simple_backtest(self, df) -> tuple:
        """简单多空回测：信号 1 做多 -1 做空，按 close 换仓，算收益率序列与夏普"""
        if df is None or len(df) < 2:
            return 0.0, 0.0
        signal = df["signal"].fillna(0).astype(int)
        close = df["close"].astype(float)
        rets = close.pct_change()
        # 持仓收益：position * ret
        position = signal.shift(1).fillna(0)
        strategy_rets = (position * rets).dropna()
        if len(strategy_rets) < 2:
            return 0.0, 0.0
        total_return = (1 + strategy_rets).prod() - 1
        sharpe = 0.0
        if strategy_rets.std() > 0:
            sharpe = float(strategy_rets.mean() / strategy_rets.std() * np.sqrt(252 * 24))  # 年化
        return float(total_return), float(sharpe)

    def _select_best(self, results: List[dict]) -> Optional[dict]:
        """按夏普选最优"""
        if not results:
            return None
        return max(results, key=lambda x: x.get("sharpe", -999))
