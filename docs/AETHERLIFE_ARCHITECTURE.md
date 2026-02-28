# AetherLife（以太生命体）— 2026 技术架构与实现路径

> 会交易的数字生命：自主感知、持续学习、自我进化，像生物一样「活着」的 AI 交易实体。

## 1. 七大维度（设计原则）

| 维度 | 目标 | 实现要点 |
|------|------|----------|
| **自主性** | Level 4–5，数小时无人工干预 | 守护层电路断路器 + 自我修复重试 |
| **实时性** | 加密/台指 &lt;10ms | 快速路径 NN/规则 + 反思路径 LLM 每秒一轮 |
| **进化性** | 每日生成新策略、优化参数、重构代码 | 进化层：反思 → 生成变体 → 回测 → 部署 |
| **记忆与连续学习** | 不遗忘历史 regime/交易 | Redis + 向量记忆 + 情景事件存储 |
| **安全与合规** | 金管会/SEC、HITL、审计 | RiskGuard、杀手开关、全量审计日志 |
| **可扩展性** | 加密、台指、美股、跨市场 | 感知层多源 Data Fabric + 统一 MarketSnapshot |
| **成本与鲁棒性** | Token/滑点/限流可控 | 语义缓存、小模型路由、容错与熔断 |

## 2. 总体架构（分层 + 闭环）

```
外部世界 ←→ 感知层 (Data Fabric)
                ↑
           记忆层 (Redis + VectorDB + 事件)
                ↑
           认知层 (Orchestrator + Worker Agents)
                ↑     ↓ 反馈
           决策层 (结构化输出 TradeIntent + 可选 RL)
                ↑
           执行层 (当前 Python / 未来 Rust NautilusTrader)
                ↑
           守护层 (RiskGuard + HITL + 审计)
                ↑
           进化层 (每日反思 → 代码/参数生成 → 回测 → 热更新)
```

## 3. 项目结构（代码骨架）

```
src/aetherlife/
├── __init__.py          # AetherLife 入口
├── config.py            # 各层配置 dataclass
├── run.py               # Phase 0 MVP 启动入口
├── perception/          # 感知层
│   ├── models.py        # MarketSnapshot, OrderBookSlice, OHLCVCandle
│   └── fabric.py        # DataFabric：多源 → 统一快照
├── memory/              # 记忆层
│   └── store.py         # MemoryStore：事件 + 决策 + LLM 上下文
├── cognition/           # 认知层
│   ├── schemas.py       # Pydantic TradeIntent, Vote
│   ├── agents.py        # MarketMaker, RiskGuard, OrderFlow, StatArb, NewsSentiment
│   └── orchestrator.py  # 多 Agent 并行 + 加权聚合 + 否决
├── guard/               # 守护层
│   └── risk_guard.py    # 电路断路器、HITL、审计
├── evolution/           # 进化层
│   └── engine.py        # 每日反思 → 变体生成 → 回测 → 选优
└── core/
    └── life.py          # 主循环：one_cycle() + run()
```

## 4. 技术选型（2026 生产级）

| 层级 | 首选 | 备选 | 说明 |
|------|------|------|------|
| 认知 | LangGraph + CrewAI | AutoGen | 状态机 + 角色分工，本仓库 Phase 0 为自研 Orchestrator |
| 执行 | Rust (NautilusTrader) | C++/FPGA | Phase 0 用现有 Python exchange_client，Phase 2 接入 Rust |
| 记忆 | Redis + pgvector | Pinecone | Phase 0 内存 MemoryStore，Phase 1+ Redis |
| 流数据 | Redpanda + ClickHouse | Kafka | Phase 0 轮询 DataFabric，Phase 1+ WebSocket/Kafka |
| 进化 | LLM 代码生成 + Genetic + PPO | AgentEvolver 论文 | Phase 0 仅框架，Phase 3 闭环 |

## 5. 落地阶段（3 个月见 MVP）

- **Phase 0（当前）**：单周期多 Agent（Python）  
  - DataFabric 轮询订单簿 + K 线 + Ticker  
  - MemoryStore 内存事件/决策，可选 Redis（`persist_to_redis` / `load_from_redis`）  
  - Orchestrator + 4 个 Worker Agent + **辩论工作流（Bull/Bear/Judge）**（`cognition.debate_enabled=true`）  
  - 结构化 TradeIntent → RiskGuard 检查 → 审计写入 `guard.audit_log_path`（默认 `logs/aetherlife_audit.jsonl`）  
  - **进化层**：每日 `evolution_hour_utc` 触发，参数变体（突破/RSI）+ 简单回测 → 按夏普选优  
  - 支持从项目根运行并加载 `configs/aetherlife.json`  
  - 运行：`cd src && python -m aetherlife.run` 或 `python src/aetherlife/run.py`

- **Phase 1（2–4 周）**：LangGraph 状态机 + Debate  
  - 用 LangGraph 实现 Orchestrator 状态机  
  - Bull/Bear/Judge 辩论工作流  
  - Redis 记忆 + 可选向量检索  

- **Phase 2（1–2 月）**：低延迟执行 + 记忆持久化  
  - Python 策略 → Rust 执行引擎（PyO3）或 NautilusTrader  
  - Redis + 事件存储  

- **Phase 3（第 3–6 月）**：真正「数字生命」  
  - 每日进化：反思 → LLM 生成策略变体 → 回测 → 热更新  
  - 睡眠–觉醒：低波动休眠，regime 切换唤醒  

## 6. 运行与配置

```bash
cd 合约交易系统/src
pip install -r ../requirements.txt
export AETHERLIFE_SYMBOL=BTCUSDT
export AETHERLIFE_TESTNET=true
export AETHERLIFE_INTERVAL=15
# 若实盘需 BINANCE_API_KEY, BINANCE_SECRET_KEY
python -m aetherlife.run
```

**单周期测试（不连交易所）**：可 mock 感知层或使用已缓存的 snapshot，直接跑 `life.one_cycle()` 验证认知→决策→守护链路。  
**SSL 问题**：若本机访问 Binance 测试网出现证书错误，可配置 `SSL_CERT_FILE` 或使用系统证书（如 macOS 安装 certifi 并链接）。

## 7. 进化提示词模板（供 Phase 3 LLM 使用）

```
你是 AetherLife 进化引擎。用 LangGraph + 当前策略代码，加入新闻情绪特征，
目标是把夏普比率提升 15%。输出完整可运行代码 + 测试用例。
```

---

**风险提示**：本系统为研究型「数字生命」框架，实盘需合规与风控审批，不构成投资建议。
