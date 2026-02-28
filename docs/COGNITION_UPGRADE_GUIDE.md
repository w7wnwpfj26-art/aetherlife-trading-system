# AetherLife 认知层升级指南

## 🧠 阶段2完成：认知层完善

### 新增的专业化 Agent（7个）

#### 1. **ChinaAStockAgent** - 中国A股专家 ✅

**专业领域**: 沪深A股（通过 IBKR Stock Connect）

**特殊处理**:
- ✅ 北向额度监控
- ✅ 交易时段检查（09:30-11:30, 13:00-15:00）
- ✅ 涨跌停检测（主板±10%、科创板±20%、ST±5%）
- ✅ 印花税成本计算（卖出0.1%）
- ✅ T+1 交易规则考虑

**使用示例**:
```python
from aetherlife.cognition import ChinaAStockAgent

agent = ChinaAStockAgent()

# 模拟A股快照
snapshot = MarketSnapshot(
    symbol="600000",  # 浦发银行
    exchange="SEHK",
    last_price=10.5,
    orderbook=OrderBookSlice(...)
)

intent = await agent.run(snapshot, context="northbound_quota: 45.2%")
print(f"决策: {intent.action} | 理由: {intent.reason}")
```

---

#### 2. **GlobalStockAgent** - 全球股票专家 ✅

**专业领域**: 美股、港股、国际股票

**特点**:
- ✅ 盘前盘后交易支持
- ✅ Fractional shares 考虑
- ✅ 多市场时区处理
- ✅ 流动性评估（Spread 分析）

---

#### 3. **CryptoNanoAgent** - 加密货币专家 ✅

**专业领域**: 加密货币 nano 永续合约

**特点**:
- ✅ 24/7 交易
- ✅ 高频策略适用
- ✅ 资金费率监控（TODO）
- ✅ 更激进的仓位管理

---

#### 4. **CrossMarketLeadLagAgent** - 跨市场套利专家 ✅

**专业领域**: 跨市场 Lead-Lag 效应捕捉

**策略**:
- ✅ BTC 先动 → A股/港股科技股跟随
- ✅ 美股科技股 → A股科技股
- ✅ 价格历史缓存与相关性计算
- ✅ 延迟套利信号生成

**示例**:
```python
agent = CrossMarketLeadLagAgent()

# BTC 涨 3% → 预期 A股科技股跟涨
signal = CrossMarketSignal(
    source_market=Market.CRYPTO,
    source_symbol="BTC/USDT",
    target_market=Market.A_STOCK,
    target_symbol="300750",  # 宁德时代
    signal_type="lead_lag",
    strength=0.75,
    lag_seconds=300
)
```

---

#### 5. **ForexMicroAgent** - 外汇专家 ✅

**专业领域**: 外汇 Micro 合约

**特点**:
- ✅ 货币对相关性
- ✅ 点差敏感（<10 bps）
- ✅ 日内波动捕捉

---

#### 6. **FuturesMicroAgent** - 期货专家 ✅

**专业领域**: Micro E-mini (ES/NQ)、nano BTC/ETH

**特点**:
- ✅ 展期换月处理（TODO）
- ✅ 基差分析（TODO）
- ✅ 持仓成本计算

---

#### 7. **SentimentAgent** - 情绪分析专家 ✅

**专业领域**: 多源情绪数据分析

**数据源**:
- Twitter/X
- 新闻（NewsAPI、GDELT）
- 微信公众号
- 雪球
- Reddit

**情绪分数**: -1（极度悲观）到 +1（极度乐观）

---

## 🎯 EnhancedOrchestrator（增强版编排器）

### 核心功能

1. **多市场自动推断**
   - 根据交易所和品种自动判断市场类型
   - 动态选择相关 Agent

2. **并行 Agent 执行**
   - 使用 `asyncio.gather` 并行调用
   - 异常处理和容错

3. **智能聚合决策**
   - 加权平均算法
   - 按 action 分组统计
   - 限制最大仓位（20%）

4. **动态权重调整**
   - Agent 权重（0-2.0）
   - 市场权重（0-1.0）
   - 实时性能反馈

### 使用示例

```python
from aetherlife.cognition import EnhancedOrchestrator, Market
from aetherlife.memory import MemoryStore

# 创建 Orchestrator
orchestrator = EnhancedOrchestrator(
    enable_specialized_agents=True,  # 启用7个专业化Agent
    debate_enabled=False,             # 关闭Bull/Bear辩论
    weights={
        "market_maker": 1.0,
        "crypto_nano": 1.5,           # 加密货币Agent权重更高
        "sentiment": 1.2
    }
)

# 创建记忆
memory = MemoryStore()

# 执行决策
final_intent = await orchestrator.run(
    snapshot=market_snapshot,
    memory=memory,
    market=Market.CRYPTO  # 可选，自动推断
)

print(f"决策: {final_intent.action}")
print(f"仓位: {final_intent.quantity_pct:.2%}")
print(f"理由: {final_intent.reason}")
print(f"置信度: {final_intent.confidence:.2f}")
```

### 动态调整示例

```python
# 提高情绪分析权重
orchestrator.update_agent_weights("sentiment", 2.0)

# 降低加密货币市场权重（熊市时）
orchestrator.update_market_weights(Market.CRYPTO, 0.6)

# 再次决策
new_intent = await orchestrator.run(snapshot, memory)
```

---

## 📊 扩展的数据模型

### TradeIntent（交易意图）

```python
TradeIntent(
    action=Action.BUY,
    market=Market.A_STOCK,
    symbol="600000",
    quantity_pct=0.08,
    reason="A股买盘压力",
    confidence=0.65,
    
    # 风控
    stop_loss_pct=0.02,
    take_profit_pct=0.05,
    
    # 执行参数
    order_type="LIMIT",
    limit_price=10.50,
    
    # 元数据
    agent_id="china_astock",
    metadata={
        "northbound_quota_pct": 45.2,
        "near_limit_up": False
    }
)
```

### DecisionContext（决策上下文）

```python
DecisionContext(
    symbol="600000",
    market=Market.A_STOCK,
    last_price=10.5,
    bid_price=10.48,
    ask_price=10.52,
    spread_bps=38,
    
    # 持仓信息
    current_position=0.10,
    unrealized_pnl=150.0,
    
    # 市场状态
    volume_24h=1000000,
    volatility=0.015,
    trend="up",
    
    # 情绪
    sentiment_score=0.75,
    news_count=15,
    
    # 风控
    daily_pnl_pct=2.5,
    max_drawdown=1.2,
    
    # A股特殊字段
    northbound_quota_pct=45.2,
    limit_up_price=11.55,
    limit_down_price=9.45
)
```

### CrossMarketSignal（跨市场信号）

```python
CrossMarketSignal(
    source_market=Market.CRYPTO,
    source_symbol="BTC/USDT",
    target_market=Market.A_STOCK,
    target_symbol="300750",
    
    signal_type="lead_lag",
    strength=0.75,
    
    lag_seconds=300,
    correlation=0.68,
    
    suggested_action=Action.BUY,
    reason="BTC 涨3%，预期A股科技股跟随"
)
```

---

## 🚀 快速开始

### 1. 运行演示脚本

```bash
# 认知层多 Agent 演示
python scripts/cognition_multi_agent_demo.py
```

演示内容：
- 单个 Agent 决策（4个示例）
- Orchestrator 多 Agent 协作（2个场景）
- 动态权重调整（3个对比）

### 2. 集成到 AetherLife

```python
# 在 aetherlife/core/life.py 中使用
from aetherlife.cognition import EnhancedOrchestrator

class AetherLife:
    def __init__(self, config):
        # 使用增强版 Orchestrator
        self._orchestrator = EnhancedOrchestrator(
            enable_specialized_agents=True,
            debate_enabled=config.cognition.debate_enabled
        )
    
    async def one_cycle(self):
        snapshot = await self._fabric.get_snapshot(self.config.symbol)
        intent = await self._orchestrator.run(snapshot, self._memory)
        # ... 执行 intent
```

---

## 📋 阶段2完成清单

- ✅ 扩展 `schemas.py`（8个新数据模型）
- ✅ 实现 7 个专业化 Agent
- ✅ 增强版 Orchestrator
- ✅ 多市场支持（6种市场类型）
- ✅ 跨市场信号检测
- ✅ 动态权重调整
- ✅ 演示脚本和文档

---

## 🔜 下一步：阶段3 - 决策层构建

1. **强化学习环境**（Gymnasium）
2. **PPO/SAC 算法**（stable-baselines3）
3. **奖励函数设计**（含滑点预测）
4. **模型训练流程**

---

## ⚠️ 注意事项

### LangGraph 集成（Phase 1+）

当前实现是为 LangGraph 预留接口的过渡版本。完整的 LangGraph 状态机将在后续版本实现：

```python
# 未来的 LangGraph 实现
from langgraph.graph import StateGraph

graph = StateGraph(LangGraphState)
graph.add_node("perception", perception_node)
graph.add_node("agents", agents_node)
graph.add_node("risk_check", risk_check_node)
graph.add_node("execution", execution_node)
graph.set_entry_point("perception")
graph.add_edge("perception", "agents")
graph.add_conditional_edges("risk_check", should_execute)
```

### LLM 集成（Phase 1+）

当前 Agent 使用规则和启发式。LLM 推理将在后续集成：

```python
# 未来的 LLM Agent
class LLMEnhancedAgent(BaseAgent):
    def __init__(self, llm):
        self.llm = llm  # LangChain LLM
    
    async def run(self, snapshot, context):
        prompt = f"市场快照: {snapshot}\n历史: {context}\n请决策"
        response = await self.llm.ainvoke(prompt)
        return parse_trade_intent(response)
```

---

## 🐛 故障排查

### Agent 执行失败
```
错误: Agent returned None
解决: 检查 snapshot.orderbook 是否为 None
```

### 聚合决策为 HOLD
```
原因: 所有 Agent 得分过低
解决: 降低阈值或调整 Agent 权重
```

### 跨市场信号缺失
```
原因: 价格历史数据不足
解决: 运行系统至少5分钟累积数据
```

---

## 📖 参考

- [多Agent系统设计模式](https://microsoft.github.io/autogen/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Pydantic 数据验证](https://docs.pydantic.dev/)
