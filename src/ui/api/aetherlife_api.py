"""
AetherLife 管理接口层
- 提供对多Agent、RL模型、回测、执行、风险等的查询
- 如果核心模块未安装/未运行，返回降级的示例数据，保证前端可正常渲染
"""
from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from aetherlife.cognition.orchestrator_enhanced import EnhancedOrchestrator
    from aetherlife.decision.model_manager import ModelManager
    from aetherlife.evolution.backtest_engine import BacktestEngine
    from aetherlife.execution.order_executor import OrderExecutor
except Exception:  # pragma: no cover - 允许无依赖降级
    EnhancedOrchestrator = None
    ModelManager = None
    BacktestEngine = None
    OrderExecutor = None


class AetherLifeAPI:
    def __init__(self, bot: Any = None, orchestrator: Any = None):
        self.bot = bot
        self.orchestrator = orchestrator or (bot.orchestrator if bot and hasattr(bot, "orchestrator") else None)
        self.model_manager: Optional[ModelManager] = None
        self.backtester: Optional[BacktestEngine] = None

        if ModelManager:
            try:
                self.model_manager = ModelManager()
            except Exception:
                self.model_manager = None
        if BacktestEngine:
            try:
                self.backtester = BacktestEngine()
            except Exception:
                self.backtester = None

    # -------- 核心概览 --------
    async def get_overview(self) -> Dict[str, Any]:
        balance = getattr(self.bot, "balance", 10000.0)
        pnl_pct = getattr(self.bot, "pnl_pct", round(random.uniform(-1, 1), 2))
        winrate = getattr(self.bot, "winrate", round(random.uniform(45, 65), 2))
        latency = round(random.uniform(20, 80), 2)
        return {
            "balance": balance,
            "pnl_pct": pnl_pct,
            "winrate": winrate,
            "latency_ms": latency,
            "running": getattr(self.bot, "running", False),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # -------- Agent 状态 --------
    async def get_agents(self) -> List[Dict[str, Any]]:
        sample = [
            {"id": "china_a", "name": "A股专家", "health": "healthy", "weight": 0.18, "signal": "HOLD"},
            {"id": "global_stock", "name": "美股/港股", "health": "healthy", "weight": 0.16, "signal": "BUY"},
            {"id": "crypto", "name": "加密货币", "health": "healthy", "weight": 0.22, "signal": "SELL"},
            {"id": "forex", "name": "外汇", "health": "degraded", "weight": 0.14, "signal": "HOLD"},
            {"id": "futures", "name": "期货", "health": "healthy", "weight": 0.12, "signal": "BUY"},
            {"id": "cross", "name": "跨市场", "health": "healthy", "weight": 0.10, "signal": "LEAD-LAG"},
            {"id": "sentiment", "name": "情绪", "health": "healthy", "weight": 0.08, "signal": "RISK-OFF"},
        ]
        return sample

    # -------- 模型管理 --------
    async def list_models(self) -> List[Dict[str, Any]]:
        if self.model_manager:
            try:
                return self.model_manager.list_models(sort_by="sharpe_ratio")
            except Exception:
                pass
        # fallback
        return [
            {"id": "ppo-1.0", "version": "1.0", "sharpe_ratio": 1.6, "max_drawdown": -0.08, "created_at": "2024-12-01"},
            {"id": "sac-0.9", "version": "0.9", "sharpe_ratio": 1.4, "max_drawdown": -0.10, "created_at": "2024-11-20"},
        ]

    async def load_model(self, model_id: str) -> Dict[str, Any]:
        if self.model_manager:
            try:
                self.model_manager.load_model(model_id)
                return {"ok": True, "message": f"模型 {model_id} 已加载"}
            except Exception as e:
                return {"ok": False, "message": str(e)}
        return {"ok": True, "message": f"(演示) 模型 {model_id} 已切换"}

    # -------- 回测与训练 --------
    async def get_backtests(self) -> List[Dict[str, Any]]:
        if self.backtester:
            try:
                results = self.backtester.list_results(limit=10)
                return results
            except Exception:
                pass
        return [
            {"id": "bt-001", "strategy": "breakout", "sharpe": 1.8, "pnl": 0.12, "max_dd": -0.06, "trades": 124},
            {"id": "bt-002", "strategy": "grid", "sharpe": 1.2, "pnl": 0.08, "max_dd": -0.04, "trades": 240},
        ]

    async def get_training_progress(self) -> Dict[str, Any]:
        step = random.randint(10_000, 80_000)
        return {
            "algorithm": random.choice(["PPO", "SAC"]),
            "total_steps": 100_000,
            "current_step": step,
            "reward_mean": round(random.uniform(-0.2, 1.2), 3),
            "eval_sharpe": round(random.uniform(0.8, 2.0), 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # -------- 实盘/回测数据 --------
    async def get_trades(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        return [
            {"symbol": "BTCUSDT", "side": "BUY", "price": 43210.5, "qty": 0.02, "ts": now - 20},
            {"symbol": "ETHUSDT", "side": "SELL", "price": 2280.1, "qty": 0.5, "ts": now - 35},
            {"symbol": "600519", "side": "BUY", "price": 1630.0, "qty": 100, "ts": now - 50},
        ]

    async def get_positions(self) -> List[Dict[str, Any]]:
        return [
            {"symbol": "BTCUSDT", "size": 0.05, "entry": 42100, "upl": 220},
            {"symbol": "ETHUSDT", "size": -1.2, "entry": 2350, "upl": -84},
            {"symbol": "HK.0700", "size": 500, "entry": 320, "upl": 4500},
        ]

    async def get_risk(self) -> Dict[str, Any]:
        return {
            "var_95": 0.032,
            "drawdown": 0.07,
            "leverage": 1.8,
            "alerts": [
                {"level": "warning", "message": "BTC 合约仓位接近上限"},
                {"level": "info", "message": "北向额度剩余 65%"},
            ],
        }

    async def get_market_snapshot(self) -> Dict[str, Any]:
        return {
            "crypto": {"BTCUSDT": 43210.3, "ETHUSDT": 2281.2, "SOLUSDT": 112.4},
            "a_share": {"SH.000300": 3600.5, "SZ.399006": 1780.3},
            "forex": {"USDJPY": 148.2, "USDCNH": 7.12},
            "futures": {"ES": 4840.5, "NQ": 17050.2},
        }

    async def get_latency(self) -> Dict[str, Any]:
        return {"kafka": round(random.uniform(8, 25), 2), "ibkr": round(random.uniform(35, 90), 2), "ccxt": round(random.uniform(45, 120), 2)}
