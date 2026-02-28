# 🚀 AetherLife 部署检查清单

## ✅ 已完成项

### 1. 代码质量
- [x] 所有语法错误已修复
  - `crypto_connector.py`: 参数顺序修正
  - `requirements.txt`: backtracking → backtesting
  - `evolution/__init__.py`: 可选依赖不阻塞启动
- [x] 导入测试通过
  - 主系统：trading_bot, data_fetcher, strategies, exchange_client
  - AetherLife：所有6层模块正常导入
- [x] 配置验证通过
  - AetherLifeConfig.from_dict() 正常工作
  - 默认配置校验通过

### 2. 核心功能实现
- [x] **感知层**（Phase 1）
  - IBKR连接器（股票/A股/期货/外汇）
  - 加密货币WebSocket（Binance/Bybit/OKX）
  - Kafka数据管道
  - Redis向量存储
  - ClickHouse时序数据库
  
- [x] **认知层**（Phase 2）
  - 7个专业化Agent
  - EnhancedOrchestrator（动态权重）
  - LangGraph状态机预留
  
- [x] **决策层**（Phase 3）
  - Gymnasium交易环境
  - PPO/SAC训练器
  - 奖励函数塑形
  - 模型管理器（版本控制、回滚）
  
- [x] **执行层**（Phase 4）
  - 智能路由器
  - 订单拆分器（TWAP/VWAP/Iceberg）
  - 执行引擎
  
- [x] **进化层**（Phase 5核心）
  - 回测引擎
  - EvolutionEngine调度器
  
- [x] **守护层**（Phase 0基础）
  - RiskGuard风控
  - 审计日志
  - HITL人工确认

### 3. 文档完善
- [x] QUICK_START.md（30分钟上手）
- [x] PERCEPTION_UPGRADE_GUIDE.md
- [x] COGNITION_UPGRADE_GUIDE.md
- [x] DECISION_LAYER_GUIDE.md
- [x] 系统检查报告.md

### 4. 记忆恢复
- [x] Redis记忆持久化
- [x] 启动时自动加载（已在life.py第137-141行实现）

---

## 📋 部署前必查项

### A. 环境配置（20分钟）

#### 1. Python环境
```bash
# 检查Python版本（需要3.10+）
python --version

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

#### 2. 基础服务（Docker）
```bash
# 启动Kafka、Redis、ClickHouse
cd docker
docker-compose up -d

# 验证服务
docker-compose ps
# 预期：3个服务均为Up状态
```

#### 3. 配置文件
```bash
# 创建配置（从模板复制）
cp configs/config.json.example configs/config.json
cp configs/aetherlife.yaml.example configs/aetherlife.yaml

# 编辑配置，填写API密钥
vim configs/aetherlife.yaml
```

**必填项**：
- `execution.api_key`: Binance API Key
- `execution.secret_key`: Binance Secret Key
- `execution.testnet`: true（强烈建议先用测试网）
- `memory.redis_url`: redis://localhost:6379（如果用Docker默认即可）

#### 4. IBKR配置（如果交易A股/美股）
```bash
# 下载并启动TWS/Gateway
# 纸上交易端口：7497
# 实盘端口：7496

# TWS中启用API：
# File → Global Configuration → API → Settings
# ☑ Enable ActiveX and Socket Clients
# ☑ Read-Only API
```

---

### B. 功能验证（30分钟）

#### 1. 导入测试
```bash
# 测试所有模块导入
python -c "
from aetherlife import AetherLife, AetherLifeConfig
from aetherlife.perception import IBKRConnector, CryptoConnector
from aetherlife.cognition import EnhancedOrchestrator
from aetherlife.decision import TradingEnv, PPOTrainer
from aetherlife.execution import SmartRouter
from aetherlife.evolution import EvolutionEngine
print('✓ 所有模块导入成功')
"
```

#### 2. 连接测试
```bash
# 测试加密货币连接（需要网络）
python scripts/perception_connector_demo.py

# 测试IBKR连接（需要TWS运行）
python -c "
import asyncio
from aetherlife.perception import IBKRConnector
async def test():
    conn = IBKRConnector(host='127.0.0.1', port=7497)
    conn.connect()
    print('✓ IBKR连接成功')
    conn.disconnect()
asyncio.run(test())
"
```

#### 3. Agent决策测试
```bash
# 测试多Agent协作
python scripts/cognition_multi_agent_demo.py
```

#### 4. RL训练测试
```bash
# 快速训练1000步（约1分钟）
python scripts/train_rl_model.py --timesteps 1000 --verbose 2

# 检查是否生成模型
ls -la models/
```

---

### C. 模拟运行（1小时）

#### 1. 纸上交易模式
```bash
# 启动后台管理（可选）
python start_admin.py

# 运行AetherLife（模拟模式，不实际下单）
cd src
python -m aetherlife.run --dry-run --interval 60
```

**观察点**：
- ✅ 数据正常接收（每60秒一次循环）
- ✅ Agent决策输出（日志中显示TradeIntent）
- ✅ 守护层检查生效（风控拦截异常决策）
- ✅ 记忆正常写入Redis

#### 2. 日志检查
```bash
# 查看实时日志
tail -f logs/aetherlife.log

# 查看审计日志
tail -f logs/audit.log

# 查看错误
grep ERROR logs/aetherlife.log
```

#### 3. 监控面板
```bash
# 访问管理界面
open http://localhost:8080

# TensorBoard（如果在训练RL模型）
tensorboard --logdir ./logs/tensorboard
open http://localhost:6006
```

---

## 🚨 安全检查

### 1. 风控参数验证
```python
# 检查配置（configs/aetherlife.yaml）
guard:
  circuit_breaker_pct: 5.0      # 单日最大回撤5%
  max_daily_loss_pct: 2.0       # 每日最大亏损2%
  hitl_enabled: true            # 启用人工确认
  hitl_threshold_usd: 100       # 超过$100需人工确认
```

### 2. 仓位限制
```python
decision:
  max_position: 1.0             # 最大仓位100%（全仓）
  enable_shorting: false        # 禁止做空
  
cognition:
  agent_weights:                # Agent权重总和=1.0
    crypto: 0.35
    astock: 0.25
    ...
```

### 3. 交易频率
```python
# 主循环间隔（src/aetherlife/run.py）
interval_seconds: 60            # 建议≥60秒（避免过度交易）
```

---

## 📊 性能基准

### 预期指标（纸上交易1周后）

| 指标 | 目标值 | 说明 |
|------|--------|------|
| Sharpe Ratio | > 1.0 | 风险调整后收益 |
| Max Drawdown | < 10% | 最大回撤 |
| Win Rate | > 50% | 胜率 |
| 执行延迟 | < 500ms | 决策到下单 |
| 数据延迟 | < 100ms | WebSocket实时性 |

### 监控命令
```bash
# 查看模型性能
python -c "
from aetherlife.decision import ModelManager
manager = ModelManager()
models = manager.list_models(sort_by='sharpe_ratio')
for m in models[:5]:
    print(f'{m.model_id}: Sharpe={m.performance_metrics.get(\"sharpe_ratio\", 0):.2f}')
"

# 查看执行统计
python -c "
from aetherlife.execution import OrderExecutionEngine
engine = OrderExecutionEngine(enable_dry_run=True)
# ... 运行一段时间后
stats = engine.get_statistics()
print(f'成功率: {stats[\"success_rate\"]:.2f}%')
print(f'平均手续费: ${stats[\"average_commission\"]:.2f}')
"
```

---

## 🔄 实盘前最后检查

### 1. 资金准备
- [ ] 测试账户余额充足（建议$1000起步）
- [ ] 设置独立API Key（只给交易权限，不给提现权限）
- [ ] IP白名单（Binance API设置）

### 2. 风控确认
- [ ] 单笔最大金额：$50
- [ ] 每日最大亏损：2%
- [ ] 最大回撤触发：5%（自动停止交易）
- [ ] HITL确认：$100以上订单

### 3. 应急预案
- [ ] 手动停止命令：`Ctrl+C` 或发送 `SIGTERM`
- [ ] 紧急平仓脚本：`python scripts/emergency_close_all.py`
- [ ] 备份联系方式：Telegram/Email告警
- [ ] 日志备份：自动归档到S3/OSS

### 4. 监控告警
- [ ] 配置Prometheus监控（可选）
- [ ] 配置Grafana仪表盘（可选）
- [ ] 邮件/Telegram告警（VaR超限、回撤超限）

---

## 🎯 实盘部署步骤

### Step 1: 切换到实盘配置
```yaml
# configs/aetherlife.yaml
execution:
  testnet: false              # ⚠️ 切换到实盘
  exchange: "binance"
  api_key: "YOUR_REAL_API_KEY"
  secret_key: "YOUR_REAL_SECRET"

# 初始仓位保守配置
cognition:
  agent_weights:
    crypto: 0.10              # 只用10%资金交易加密货币
    # 其他市场暂时禁用
```

### Step 2: 小仓位试运行（1周）
```bash
# 启动实盘（最小仓位）
cd src
python -m aetherlife.run --interval 300  # 5分钟一次

# 每日检查
python scripts/daily_report.py
```

### Step 3: 逐步扩容
- **第1周**：10%资金，每日最大亏损1%
- **第2周**：20%资金，每日最大亏损1.5%
- **第4周**：35%资金，每日最大亏损2%
- **第8周**：全仓，根据表现调整

### Step 4: 持续优化
```bash
# 每周重新训练RL模型
python scripts/train_rl_model.py --timesteps 200000

# 每月回测验证
python scripts/backtest_all_strategies.py

# 每季度架构review
```

---

## 📞 技术支持

### 问题排查
1. **连接失败**：检查网络、API密钥、IP白名单
2. **导入错误**：`pip install -r requirements.txt --upgrade`
3. **Redis连接失败**：`docker-compose up -d redis`
4. **RL训练不收敛**：降低学习率、调整奖励函数

### 日志位置
- 主日志：`logs/aetherlife.log`
- 审计日志：`logs/audit.log`
- 错误日志：`logs/error.log`
- TensorBoard：`logs/tensorboard/`

### 常用命令
```bash
# 查看系统状态
python -c "from aetherlife import AetherLife; life = AetherLife(); print(life.config)"

# 查看模型列表
python -c "from aetherlife.decision import ModelManager; print(ModelManager().list_models())"

# 查看记忆统计
python -c "from aetherlife.memory import MemoryStore; store = MemoryStore(); print(store.get_stats())"
```

---

## ✅ 最终确认

在执行 `python -m aetherlife.run` 前，请确认：

- [ ] ✅ 所有依赖已安装
- [ ] ✅ Docker服务已启动
- [ ] ✅ API密钥已配置
- [ ] ✅ 测试网模式已验证
- [ ] ✅ 风控参数已设置
- [ ] ✅ 日志目录已创建
- [ ] ✅ 监控面板可访问
- [ ] ✅ 应急预案已准备

---

## 🎉 开始交易

```bash
# 最后一次检查
python -c "from aetherlife import AetherLife; print('✓ 系统就绪')"

# 启动AetherLife
cd src
python -m aetherlife.run

# 在另一个终端查看日志
tail -f logs/aetherlife.log
```

**祝交易顺利！May the Aether be with you! 🚀✨**

---

*生成时间: 2025-02-21*  
*版本: v1.0 MVP*  
*状态: ✅ 生产就绪*
