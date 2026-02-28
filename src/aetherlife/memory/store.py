"""
记忆存储：内存为主 + 可选 Redis 持久化
Phase 0：纯内存；Phase 1+：Redis 列表持久化 + Vector
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import deque
import json

try:
    import redis.asyncio as redis_async
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


@dataclass
class TradeEvent:
    """单笔交易事件（情景记忆）"""
    symbol: str
    side: str  # BUY / SELL
    quantity: float
    price: float
    pnl: Optional[float] = None
    reason: str = ""  # signal | stop_loss | take_profit
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecision:
    """单次 Agent 决策记录（审计 + 反思）"""
    agent_id: str
    action: str  # HOLD | BUY | SELL
    confidence: float
    reasoning: str
    snapshot_time: datetime = field(default_factory=datetime.utcnow)
    market_summary: Optional[Dict[str, Any]] = None


class MemoryStore:
    """短期 + 情景记忆（可选 Redis 持久化）"""

    REDIS_KEY_TRADES = "aetherlife:trades"
    REDIS_KEY_SHORT_TERM = "aetherlife:short_term"
    REDIS_MAX_LIST = 5000

    def __init__(self, max_events: int = 5000, redis_url: Optional[str] = None):
        self.max_events = max_events
        self.redis_url = redis_url
        self._trade_events: deque = deque(maxlen=max_events)
        self._decisions: deque = deque(maxlen=max_events)
        # 修复：使用 deque(maxlen=) 代替 list + pop(0)，尾部追加/头部淘汰均为 O(1)
        self._short_term: deque = deque(maxlen=100)
        self._redis: Optional[Any] = None
        if redis_url and _REDIS_AVAILABLE:
            try:
                self._redis = redis_async.from_url(redis_url, decode_responses=True)
            except Exception:
                self._redis = None

    def add_trade(self, event: TradeEvent):
        self._trade_events.append(event)
        # deque(maxlen=100) 自动淘汰最旧条目，无需手动 pop(0)
        self._short_term.append({
            "type": "trade",
            "ts": event.timestamp.isoformat(),
            "symbol": event.symbol,
            "side": event.side,
            "pnl": event.pnl,
        })

    def add_decision(self, d: AgentDecision):
        self._decisions.append(d)
        self._short_term.append({
            "type": "decision",
            "ts": d.snapshot_time.isoformat(),
            "agent": d.agent_id,
            "action": d.action,
            "reasoning": d.reasoning[:200],
        })

    async def persist_to_redis(self):
        """将近期事件写入 Redis（可选，在 shutdown 或定时调用）"""
        if self._redis is None:
            return
        try:
            for e in list(self._trade_events)[-500:]:
                item = {"type": "trade", "ts": e.timestamp.isoformat(), "symbol": e.symbol, "side": e.side, "pnl": e.pnl}
                await self._redis.rpush(self.REDIS_KEY_TRADES, json.dumps(item, default=str))
            await self._redis.ltrim(self.REDIS_KEY_TRADES, -self.REDIS_MAX_LIST, -1)
            for item in self._short_term[-100:]:
                await self._redis.rpush(self.REDIS_KEY_SHORT_TERM, json.dumps(item, default=str))
            await self._redis.ltrim(self.REDIS_KEY_SHORT_TERM, -500, -1)
        except Exception:
            pass

    async def load_from_redis(self):
        """从 Redis 加载近期事件到内存（可选，在 startup 调用）"""
        if self._redis is None:
            return
        try:
            raw = await self._redis.lrange(self.REDIS_KEY_TRADES, -200, -1)
            for s in raw:
                try:
                    data = json.loads(s)
                    ts = datetime.fromisoformat(data["ts"].replace("Z", "+00:00")) if data.get("ts") else datetime.utcnow()
                    self._trade_events.append(TradeEvent(
                        symbol=data.get("symbol", ""),
                        side=data.get("side", ""),
                        quantity=0,
                        price=0,
                        pnl=data.get("pnl"),
                        timestamp=ts,
                    ))
                except Exception:
                    pass
        except Exception:
            pass

    def get_recent_trades(self, n: int = 50) -> List[TradeEvent]:
        return list(self._trade_events)[-n:]

    def get_recent_decisions(self, n: int = 50) -> List[AgentDecision]:
        return list(self._decisions)[-n:]

    def get_context_for_llm(self, max_items: int = 30) -> str:
        """供 LLM 的短期记忆摘要"""
        # deque 不支持负切片，先转 list 再取最近 N 条
        items = list(self._short_term)[-max_items:]
        lines = [f"- [{x.get('ts', '')}] {x.get('type', '')}: {json.dumps(x, ensure_ascii=False)}" for x in items]
        return "\n".join(lines) if lines else "(无近期事件)"

    def get_daily_pnl(self) -> float:
        today = datetime.utcnow().date()
        return sum(
            e.pnl or 0 for e in self._trade_events
            if e.timestamp.date() == today
        )

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
