"""
决策层结构化输出：Pydantic 保证可解析、可审计
扩展支持多市场、LangGraph 状态
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class Action(str, Enum):
    """交易动作"""
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"  # 平仓


class Market(str, Enum):
    """市场类型"""
    CRYPTO = "CRYPTO"
    A_STOCK = "A_STOCK"  # 中国A股
    HK_STOCK = "HK_STOCK"  # 香港股票
    US_STOCK = "US_STOCK"  # 美股
    INTL_STOCK = "INTL_STOCK"  # 国际股票
    FOREX = "FOREX"  # 外汇
    FUTURES = "FUTURES"  # 期货
    COMMODITIES = "COMMODITIES"  # 商品


class TradeIntent(BaseModel):
    """
    单次交易意图（LLM/RL 输出必须符合此 schema）
    扩展支持多市场
    """
    action: Action = Action.HOLD
    market: Market = Market.CRYPTO
    symbol: str = "BTCUSDT"
    quantity_pct: float = Field(default=0.0, ge=0, le=1, description="仓位比例 0~1")
    reason: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    
    # 风控参数
    stop_loss_pct: Optional[float] = Field(default=None, ge=0, le=1)
    take_profit_pct: Optional[float] = Field(default=None, ge=0, le=1)
    
    # 时效性
    valid_until: Optional[datetime] = None
    
    # 执行参数
    order_type: str = Field(default="MARKET", description="MARKET/LIMIT/FOK/IOC/POST_ONLY")
    limit_price: Optional[float] = None
    
    # 元数据
    agent_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class Vote(BaseModel):
    """辩论工作流：多方投票"""
    role: str  # bull | bear | judge | agent_name
    action: Action = Action.HOLD
    market: Market = Market.CRYPTO
    reasoning: str = ""
    confidence: float = Field(ge=0, le=1)
    
    # 投票时间
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentState(str, Enum):
    """Agent 状态"""
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    DECIDED = "DECIDED"
    ERROR = "ERROR"


class DecisionContext(BaseModel):
    """
    决策上下文（供 Agent 使用的输入）
    """
    # 市场快照
    symbol: str
    market: Market
    last_price: float
    
    # 订单簿
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    spread_bps: Optional[float] = None
    
    # 持仓信息
    current_position: float = 0.0  # 当前持仓比例
    unrealized_pnl: float = 0.0
    
    # 市场状态
    volume_24h: Optional[float] = None
    volatility: Optional[float] = None
    trend: Optional[str] = None  # up/down/sideways
    
    # 情绪数据
    sentiment_score: Optional[float] = None
    news_count: Optional[int] = None
    
    # 风控状态
    daily_pnl_pct: float = 0.0
    max_drawdown: float = 0.0
    
    # 记忆上下文（文本）
    memory_context: str = ""
    
    # 特殊字段（A股专用）
    northbound_quota_pct: Optional[float] = None  # 北向额度剩余百分比
    limit_up_price: Optional[float] = None  # 涨停价
    limit_down_price: Optional[float] = None  # 跌停价
    
    # 时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LangGraphState(BaseModel):
    """
    LangGraph 状态机的全局状态
    """
    # 输入：市场数据
    contexts: Dict[str, DecisionContext] = Field(default_factory=dict)  # symbol -> context
    
    # Agent 决策结果
    agent_intents: List[TradeIntent] = Field(default_factory=list)
    agent_states: Dict[str, AgentState] = Field(default_factory=dict)  # agent_id -> state
    
    # 辩论结果（可选）
    debate_votes: List[Vote] = Field(default_factory=list)
    debate_result: Optional[TradeIntent] = None
    
    # 风控检查
    risk_check_passed: bool = True
    veto_reason: Optional[str] = None
    
    # 强化学习决策（可选）
    rl_decision: Optional[TradeIntent] = None
    
    # 最终决策
    final_intent: Optional[TradeIntent] = None
    
    # 执行结果
    execution_result: Optional[Dict[str, Any]] = None
    
    # 错误信息
    errors: List[str] = Field(default_factory=list)
    
    # 时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True


class CrossMarketSignal(BaseModel):
    """
    跨市场信号（用于 Lead-Lag 效应）
    """
    source_market: Market
    source_symbol: str
    target_market: Market
    target_symbol: str
    
    signal_type: str  # lead_lag / correlation / arbitrage
    strength: float = Field(ge=0, le=1, description="信号强度")
    
    # Lead-Lag 参数
    lag_seconds: Optional[float] = None
    correlation: Optional[float] = None
    
    # 建议动作
    suggested_action: Action
    reason: str
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MarketRegime(str, Enum):
    """市场状态"""
    BULL = "BULL"  # 牛市
    BEAR = "BEAR"  # 熊市
    SIDEWAYS = "SIDEWAYS"  # 震荡
    HIGH_VOL = "HIGH_VOL"  # 高波动
    LOW_VOL = "LOW_VOL"  # 低波动
    CRISIS = "CRISIS"  # 危机
    UNKNOWN = "UNKNOWN"


class SentimentData(BaseModel):
    """情绪数据"""
    source: str  # twitter / news / reddit / weibo / xueqiu
    symbol: str
    
    # 情绪分数 (-1 到 1)
    sentiment_score: float = Field(ge=-1, le=1)
    
    # 原始数据
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    
    # 关键词
    keywords: List[str] = Field(default_factory=list)
    
    # 时间窗口
    time_window: str = "1h"  # 1h / 24h / 7d
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
