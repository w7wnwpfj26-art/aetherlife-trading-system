"""
AetherLife 全局配置
对应 2026 技术架构：多市场、多代理、进化闭环、合规
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import os


@dataclass
class DataFabricConfig:
    """感知层：多源数据"""
    # 交易所 WebSocket（可扩展 Binance/Bybit/OKX/TAIFEX/Fubon Neo）
    ws_exchanges: List[str] = field(default_factory=lambda: ["binance"])
    # 刷新间隔 ms（HFT <1ms，加密/台指 <10ms，本 MVP 可用 100–500ms）
    orderbook_refresh_ms: int = 100
    # 是否接入新闻/X 语义流
    enable_news_stream: bool = False
    enable_twitter_stream: bool = False


@dataclass
class MemoryConfig:
    """记忆层：Redis + 向量 + 长期存储"""
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    # 短期上下文 token 上限（LLM window）
    context_max_tokens: int = 32_000
    # 是否启用向量记忆（pgvector / Redis Vector）
    use_vector_memory: bool = False
    # 事件/交易历史保留条数
    episodic_max_events: int = 10_000


@dataclass
class CognitionConfig:
    """认知层：Orchestrator + Worker Agents"""
    # LangGraph 状态机
    orchestrator_type: str = "langgraph"  # langgraph | custom
    # Worker 角色（MarketMaker, StatArb, OrderFlow, RiskGuard, NewsSentiment）
    worker_agents: List[str] = field(default_factory=lambda: [
        "market_maker", "stat_arb", "order_flow", "risk_guard", "news_sentiment"
    ])
    # 辩论工作流：Bull / Bear / Judge
    debate_enabled: bool = True
    # 并行深度分析数
    parallel_analysts: int = 4


@dataclass
class DecisionConfig:
    """决策层：RL + 结构化输出"""
    # 决策方式：llm_structured | rl | hybrid
    decision_mode: str = "llm_structured"
    # Pydantic 交易 schema 严格校验
    strict_schema: bool = True
    # 快速路径：神经网络直接输出（低延迟）
    fast_path_nn: bool = False


@dataclass
class ExecutionConfig:
    """执行层：当前 Python，未来 Rust/NautilusTrader"""
    engine: str = "python"  # python | rust
    # 与现有 exchange_client 对接
    exchange: str = "binance"
    testnet: bool = True


@dataclass
class GuardConfig:
    """守护层：风控 + 合规"""
    # 人类在环：大额/异常需人工确认
    hitl_enabled: bool = True
    hitl_threshold_usd: float = 10_000
    # 杀手开关：回撤/单日亏损超阈值自动暂停
    circuit_breaker_pct: float = 0.05
    max_daily_loss_pct: float = 0.10
    # 审计：所有决策与执行写日志/存证
    audit_log_enabled: bool = True
    audit_log_path: Optional[str] = "logs/aetherlife_audit.jsonl"


@dataclass
class EvolutionConfig:
    """进化层：自我改进"""
    # 每日进化触发时间（UTC 小时）
    evolution_hour_utc: int = 4
    # 每轮生成策略变体数
    strategy_variants_per_round: int = 10
    # 回测后部署：仅部署夏普/收益达标者
    min_sharpe_to_deploy: float = 0.5
    # 是否允许 LLM 生成并热更新代码
    allow_code_generation: bool = True


@dataclass
class AetherLifeConfig:
    """AetherLife 总配置"""
    data: DataFabricConfig = field(default_factory=DataFabricConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    cognition: CognitionConfig = field(default_factory=CognitionConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    # 全局
    symbol: str = "BTCUSDT"
    markets: List[str] = field(default_factory=lambda: ["crypto"])  # crypto | tw_futures | us_equity
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AetherLifeConfig":
        """从字典加载（兼容 config.json）"""
        def sub(key: str, subcls):
            if key in d and isinstance(d[key], dict):
                return subcls(**d[key])
            return subcls()
        return cls(
            data=sub("data", DataFabricConfig),
            memory=sub("memory", MemoryConfig),
            cognition=sub("cognition", CognitionConfig),
            decision=sub("decision", DecisionConfig),
            execution=sub("execution", ExecutionConfig),
            guard=sub("guard", GuardConfig),
            evolution=sub("evolution", EvolutionConfig),
            symbol=d.get("symbol", "BTCUSDT"),
            markets=d.get("markets", ["crypto"]),
            log_level=d.get("log_level", "INFO"),
        )
