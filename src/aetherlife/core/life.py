"""
AetherLife 主循环：感知 → 记忆 → 认知 → 决策 → 守护 → 执行
Phase 0 MVP：可运行的单周期 + 与现有 exchange 对接
"""

import asyncio
import logging
from typing import Optional

from ..config import AetherLifeConfig
from ..perception import DataFabric, MarketSnapshot
from ..memory import MemoryStore, TradeEvent, AgentDecision
from ..cognition import Orchestrator
from ..cognition.schemas import TradeIntent, Action
from ..guard import RiskGuard

logger = logging.getLogger("aetherlife")


class AetherLife:
    """以太生命体：自主感知、决策、执行、记忆、进化"""

    def __init__(self, config: Optional[AetherLifeConfig] = None):
        self.config = config or AetherLifeConfig()
        self._fabric = DataFabric(
            exchange=self.config.execution.exchange,
            testnet=self.config.execution.testnet,
            refresh_ms=self.config.data.orderbook_refresh_ms,
        )
        self._memory = MemoryStore(
            max_events=self.config.memory.episodic_max_events,
            redis_url=self.config.memory.redis_url if self.config.memory.redis_url else None,
        )
        self._orchestrator = Orchestrator(debate_enabled=self.config.cognition.debate_enabled)
        self._guard = RiskGuard(
            circuit_breaker_pct=self.config.guard.circuit_breaker_pct,
            max_daily_loss_pct=self.config.guard.max_daily_loss_pct,
            hitl_enabled=self.config.guard.hitl_enabled,
            hitl_threshold_usd=self.config.guard.hitl_threshold_usd,
            audit_log_path=getattr(self.config.guard, "audit_log_path", None),
        )
        self._client = None
        self._evolution = None
        self._running = False
        self._last_evolution_date = None

    async def _get_client(self):
        if self._client is None:
            from execution.exchange_client import create_client
            import os
            self._client = create_client(
                self.config.execution.exchange,
                os.getenv("BINANCE_API_KEY", ""),
                os.getenv("BINANCE_SECRET_KEY", ""),
                self.config.execution.testnet,
            )
        return self._client

    async def one_cycle(self) -> TradeIntent:
        """单轮生命周期：感知 → 认知 → 决策 → 守护 → (执行)"""
        symbol = self.config.symbol
        self._fabric.set_symbol(symbol)
        # 1. 感知
        snapshot = await self._fabric.get_snapshot(symbol)
        # 2. 认知 + 决策
        intent = await self._orchestrator.run(snapshot, self._memory)
        # 3. 审计
        await self._guard.audit("decision", {
            "symbol": symbol,
            "action": intent.action,
            "reason": intent.reason,
            "confidence": intent.confidence,
        })
        # 4. 守护层检查（daily_pnl_pct 为百分比，如 -5 表示 -5%）
        daily_pnl = self._memory.get_daily_pnl()
        daily_pnl_pct = (daily_pnl / 10000 * 100) if daily_pnl else 0  # 假设基准 10000 估算
        guard_result = self._guard.check(intent, daily_pnl_pct, position_value_usd=0)
        if not guard_result.allowed:
            logger.warning("守护层拦截: %s", guard_result.reason)
            intent = TradeIntent(action=Action.HOLD, reason=guard_result.reason, confidence=0)
        if guard_result.hitl_required:
            logger.info("HITL 需人工确认，本周期不执行")
            return intent
        # 5. 执行（Phase 0：仅 HOLD 或记录意图；可接真实下单）
        if intent.action != Action.HOLD and guard_result.allowed:
            await self._execute_intent(intent, snapshot)
        return intent

    async def _execute_intent(self, intent: TradeIntent, snapshot: MarketSnapshot):
        """执行交易意图（对接现有 exchange_client）"""
        try:
            client = await self._get_client()
            price = snapshot.last_price or (snapshot.orderbook.mid_price() if snapshot.orderbook else 0)
            if price <= 0:
                return
            balance = await client.get_balance()
            total = balance.get("total") or 0
            if total <= 0:
                total = 10000  # 模拟
            size_usd = total * (intent.quantity_pct or 0.1)
            quantity = round(size_usd / price, 3)
            if quantity <= 0:
                return
            side = "BUY" if intent.action == Action.BUY else "SELL"
            result = await client.place_order(
                symbol=self.config.symbol,
                side=side,
                order_type="MARKET",
                quantity=quantity,
                leverage=10,
            )
            if result.get("success"):
                self._memory.add_trade(TradeEvent(
                    symbol=self.config.symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    reason="aetherlife_intent",
                ))
        except Exception as e:
            logger.exception("执行意图失败: %s", e)

    async def run(self, interval_seconds: float = 10):
        """主循环：持续感知-决策-执行；每日凌晨触发进化"""
        from datetime import datetime as dt
        self._running = True
        if self._evolution is None:
            from ..evolution import EvolutionEngine
            self._evolution = EvolutionEngine(
                self._memory,
                symbol=self.config.symbol,
                exchange=self.config.execution.exchange,
                testnet=self.config.execution.testnet,
                variants_per_round=self.config.evolution.strategy_variants_per_round,
                min_sharpe_to_deploy=self.config.evolution.min_sharpe_to_deploy,
            )
        if hasattr(self._memory, "load_from_redis"):
            try:
                await self._memory.load_from_redis()
            except Exception as e:
                logger.debug("从 Redis 加载记忆失败: %s", e)
        logger.info("AetherLife 启动，周期 %.1fs", interval_seconds)
        while self._running:
            try:
                now = dt.utcnow()
                if self.config.evolution.evolution_hour_utc is not None and now.hour == self.config.evolution.evolution_hour_utc:
                    if self._last_evolution_date != now.date():
                        self._last_evolution_date = now.date()
                        await self._evolution.run_daily_evolution()
                intent = await self.one_cycle()
                logger.info("本周期决策: %s | %s", intent.action, intent.reason)
            except Exception as e:
                logger.exception("周期异常: %s", e)
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False
        logger.info("AetherLife 停止")

    async def shutdown(self):
        self.stop()
        await self._fabric.close()
        if hasattr(self._memory, "persist_to_redis") and self._memory._redis:
            await self._memory.persist_to_redis()
        if hasattr(self._memory, "close"):
            await self._memory.close()
        if self._client:
            await self._client.close()
