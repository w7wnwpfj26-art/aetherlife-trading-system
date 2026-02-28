# AetherLife 快速开始指南

## 🚀 30分钟上手

### 第一步：环境准备

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建配置文件
cp configs/aetherlife.yaml.example configs/aetherlife.yaml

# 3. 配置API密钥（编辑 configs/aetherlife.yaml）
```

### 第二步：启动基础服务

```bash
# 使用Docker Compose启动Kafka、Redis、ClickHouse等
cd docker
docker-compose up -d

# 验证服务状态
docker-compose ps
```

### 第三步：运行演示脚本

#### Demo 1：感知层 - 数据连接
```bash
python scripts/perception_connector_demo.py
```

#### Demo 2：认知层 - 多Agent决策
```bash
python scripts/cognition_multi_agent_demo.py
```

#### Demo 3：决策层 - RL训练
```bash
# 快速训练（5万步，约10分钟）
python scripts/train_rl_model.py --timesteps 50000 --eval

# 查看训练进度
tensorboard --logdir ./logs/tensorboard
```

#### Demo 4：执行层 - 智能路由
```bash
python -m aetherlife.execution.smart_router
```

---

## 📖 核心模块使用

### 1. 感知层：实时数据接入

```python
from aetherlife.perception import IBKRConnector, CryptoConnector, DataPipeline

# IBKR 股票/A股/外汇/期货
ibkr = IBKRConnector(host="127.0.0.1", port=7497)  # 纸上交易
ibkr.connect()
await ibkr.subscribe_ticker("AAPL", sec_type="STK", exchange="SMART")

# 加密货币 WebSocket
crypto = CryptoConnector(exchange_id="binance")
await crypto.connect()
await crypto.subscribe_ticker("BTC/USDT")

# 统一数据流
pipeline = DataPipeline(kafka_bootstrap_servers=["localhost:9092"])
await pipeline.start()
```

### 2. 认知层：多Agent协作

```python
from aetherlife.cognition import EnhancedOrchestrator, ChinaAStockAgent

# 创建Orchestrator
orchestrator = EnhancedOrchestrator()

# 注册Agent
orchestrator.register_agent(ChinaAStockAgent(), weight=0.3)
orchestrator.register_agent(CryptoNanoAgent(), weight=0.3)

# 运行决策
snapshot = MarketSnapshot(...)
intent = await orchestrator.run(snapshot, memory_context)
print(f"最终决策: {intent.action} {intent.symbol}")
```

### 3. 决策层：强化学习训练

```python
from aetherlife.decision import TradingEnv, PPOTrainer, ModelManager

# 创建环境
env = TradingEnv(initial_balance=10000)

# 训练PPO模型
trainer = PPOTrainer(env=env, tensorboard_log="./logs")
trainer.train(total_timesteps=100000)

# 保存模型
manager = ModelManager()
model_id = manager.save_model(
    trainer=trainer,
    version="1.0",
    performance_metrics={"sharpe_ratio": 1.8}
)

# 提升到生产
manager.promote_to_production(model_id)
```

### 4. 执行层：智能路由与订单拆分

```python
from aetherlife.execution import SmartRouter, OrderSplitter, OrderExecutionEngine

# 创建路由器
router = SmartRouter()
decision = router.route(trade_intent, balance=10000)

# 拆分大单
splitter = OrderSplitter()
sub_orders = splitter.split(
    order_id="ORDER_001",
    symbol="BTCUSDT",
    action="BUY",
    total_quantity=0.5,
    current_price=50000,
    strategy=SplitStrategy.TWAP
)

# 执行
engine = OrderExecutionEngine()
results = await engine.execute(decision)
```

### 5. 进化层：策略回测

```python
from aetherlife.evolution import BacktestEngine, BacktestConfig

# 配置回测
config = BacktestConfig(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2025, 1, 1),
    initial_balance=10000
)

# 运行回测
engine = BacktestEngine(config, historical_data)
result = engine.run(my_strategy)

print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
```

---

## 🎯 完整交易流程示例

```python
import asyncio
from aetherlife.perception import MarketSnapshot
from aetherlife.cognition import EnhancedOrchestrator
from aetherlife.decision import PPOTrainer, ModelManager
from aetherlife.execution import SmartRouter, OrderExecutionEngine

async def main():
    # 1. 初始化组件
    orchestrator = EnhancedOrchestrator()
    router = SmartRouter()
    executor = OrderExecutionEngine(enable_dry_run=True)  # 模拟模式
    
    # 2. 加载RL模型
    manager = ModelManager()
    prod_model_id = manager.get_production_model()
    rl_agent = manager.load_model(prod_model_id, env=trading_env)
    
    # 3. 交易循环
    while True:
        # 获取市场快照
        snapshot = await fetch_market_snapshot()
        
        # Multi-Agent决策
        agent_intent = await orchestrator.run(snapshot, memory_context)
        
        # RL增强决策
        rl_obs = convert_to_rl_observation(snapshot)
        rl_action = rl_agent.predict(rl_obs, deterministic=True)
        
        # 融合决策
        final_intent = merge_decisions(agent_intent, rl_action)
        
        # 智能路由
        routing_decision = router.route(final_intent, balance=10000)
        
        # 执行
        results = await executor.execute(routing_decision)
        
        # 在线学习（每小时一次）
        if should_online_learn():
            rl_agent.online_learn(rl_obs, rl_action, reward, done)
        
        await asyncio.sleep(60)  # 每分钟执行一次

asyncio.run(main())
```

---

## 📊 监控和管理

### 查看模型列表
```bash
python -c "
from aetherlife.decision import ModelManager
manager = ModelManager()
for model in manager.list_models(sort_by='sharpe_ratio'):
    print(f'{model.model_id}: Sharpe={model.performance_metrics[\"sharpe_ratio\"]:.2f}')
"
```

### 对比模型性能
```python
from aetherlife.decision import ModelManager

manager = ModelManager()
comparison = manager.compare_models("ppo_v1.0_20250221", "ppo_v1.1_20250222")

for metric, data in comparison["metrics_comparison"].items():
    print(f"{metric}: {data['model1']:.4f} → {data['model2']:.4f} ({data['improvement_pct']:.2f}%)")
```

### 回滚模型
```bash
python -c "
from aetherlife.decision import ModelManager
manager = ModelManager()
manager.rollback_production()
print('已回滚到上一版本')
"
```

---

## 🔧 常见问题

### 1. IBKR连接失败

**问题**：无法连接到TWS/Gateway

**解决方案**：
- 确认TWS/Gateway已启动
- 纸上交易端口：7497
- 实盘端口：7496
- 在TWS中启用"Socket客户端连接"（File → Global Configuration → API → Settings）

### 2. Kafka启动失败

**问题**：docker-compose启动Kafka报错

**解决方案**：
```bash
# 清理旧数据
docker-compose down -v
docker-compose up -d
```

### 3. RL训练不收敛

**问题**：奖励值不增长

**解决方案**：
- 降低学习率：`--learning-rate 1e-4`
- 减少惩罚系数（编辑`aetherlife/decision/reward_shaping.py`）
- 增加训练步数：`--timesteps 200000`

### 4. A股交易时段外报错

**问题**：合规检查失败："A股交易时段外"

**解决方案**：
这是正常的合规保护，A股只在09:30-11:30和13:00-15:00可交易

---

## 📚 进阶文档

- [感知层完整指南](PERCEPTION_UPGRADE_GUIDE.md)
- [认知层完整指南](COGNITION_UPGRADE_GUIDE.md)
- [决策层完整指南](DECISION_LAYER_GUIDE.md)
- [API参考文档](API_REFERENCE.md)

---

## 🎉 下一步

1. **实盘前准备**：
   ```bash
   # 纸上交易验证（至少1周）
   python src/aetherlife/run.py --dry-run
   ```

2. **小仓位测试**：
   - 初始资金：$1000
   - 单笔风险：≤0.5%
   - 每日回撤限制：2%

3. **逐步扩容**：
   - 验证2周后增加到$5000
   - 验证1个月后增加到全部资金

4. **持续优化**：
   - 每周回测验证
   - 每月重新训练RL模型
   - 根据市场变化调整Agent权重

---

## 💬 技术支持

- 查看日志：`./logs/*.log`
- 监控面板：http://localhost:8080（启动后台后）
- TensorBoard：`tensorboard --logdir ./logs/tensorboard`

**祝交易顺利！ 🚀**
