"""
RiskGuard：电路断路器、大额 HITL、审计
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Awaitable
import logging
import os

from ..cognition.schemas import TradeIntent, Action

logger = logging.getLogger("aetherlife.guard")


@dataclass
class GuardResult:
    allowed: bool
    reason: str
    hitl_required: bool = False


class RiskGuard:
    """守护层：执行前最后一道关卡"""

    def __init__(
        self,
        circuit_breaker_pct: float = 0.05,
        max_daily_loss_pct: float = 0.10,
        hitl_enabled: bool = True,
        hitl_threshold_usd: float = 10_000,
        audit_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.circuit_breaker_pct = circuit_breaker_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.hitl_enabled = hitl_enabled
        self.hitl_threshold_usd = hitl_threshold_usd
        self._audit_callback = audit_callback
        self._audit_log_path = audit_log_path
        self._paused = False
        self._pause_reason = ""

    def set_paused(self, paused: bool, reason: str = ""):
        self._paused = paused
        self._pause_reason = reason

    def check(
        self,
        intent: TradeIntent,
        daily_pnl_pct: float,
        position_value_usd: float = 0,
    ) -> GuardResult:
        """执行前检查"""
        if self._paused:
            return GuardResult(False, f"守护层暂停: {self._pause_reason}")
        if intent.action == Action.HOLD:
            return GuardResult(True, "HOLD 无需拦截")
        # 电路断路器
        if daily_pnl_pct <= -self.circuit_breaker_pct * 100:  # 假设传入已为百分比
            return GuardResult(False, f"触发电路断路器: 日亏损 {daily_pnl_pct:.2f}%")
        if daily_pnl_pct <= -self.max_daily_loss_pct * 100:
            return GuardResult(False, f"超过单日最大亏损: {daily_pnl_pct:.2f}%")
        # 大额 HITL
        hitl = self.hitl_enabled and position_value_usd >= self.hitl_threshold_usd
        if hitl:
            return GuardResult(True, "通过但需人工确认", hitl_required=True)
        return GuardResult(True, "通过")

    async def audit(self, event_type: str, payload: dict):
        """审计日志：logger + 可选文件 + 可选 callback"""
        import json as _json
        logger.info("AUDIT %s: %s", event_type, payload)
        line = _json.dumps({"ts": datetime.utcnow().isoformat() + "Z", "event": event_type, "payload": payload}, ensure_ascii=False) + "\n"
        if self._audit_log_path:
            try:
                os.makedirs(os.path.dirname(self._audit_log_path) or ".", exist_ok=True)
                with open(self._audit_log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                logger.debug("审计写文件失败: %s", e)
        if self._audit_callback:
            await self._audit_callback(event_type, payload)
