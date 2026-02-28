# 决策层完整指南

## 概述

决策层基于强化学习（Reinforcement Learning）实现智能交易决策，核心思想是让AI通过与市场环境的交互学习最优策略。

### 核心组件

```
decision/
├── rl_env.py            # Gymnasium交易环境
├── ppo_agent.py         # PPO/SAC训练器
├── reward_shaping.py    # 奖励函数塑形
└── model_manager.py     # 模型管理器
```

---

## 1. 强化学习环境（TradingEnv）

### 1.1 基本概念

- **状态空间**（20维）：价格、持仓、PnL、技术指标
- **动作空间**：连续[-1,1]或离散(HOLD/BUY/SELL)
- **奖励函数**：PnL + Sharpe - 回撤 - 成本

### 1.2 使用示例

```python
from aetherlife.decision import TradingEnv

# 创建环境
env = TradingEnv(
    initial_balance=10000,
    commission=0.001,
    slippage=0.0005,
    max_position=1.0,
    max_steps=1000,
    action_space_type="continuous",  # 或 "discrete"
    enable_shorting=False
)

# 重置环境
obs, info = env.reset()

# 执行一步
action = np.array([0.5])  # 目标仓位50%
obs, reward, terminated, truncated, info = env.step(action)

print(f"奖励: {reward:.2f}")
print(f"当前余额: {info['balance']:.2f}")
print(f"Sharpe Ratio: {info['sharpe_ratio']:.2f}")
```

### 1.3 状态空间详解

```python
observation[0]  = 归一化价格
observation[1]  = 归一化成交量
observation[2]  = Bid-Ask Spread
observation[3]  = 持仓比例 [-1, 1]
observation[4]  = 未实现盈亏比例
observation[5:15] = 最近10步价格变化率
observation[15] = 当前Sharpe Ratio
observation[16] = RSI
observation[17] = MACD
observation[18] = 布林带位置
observation[19] = ATR
```

### 1.4 动作空间

#### 连续动作空间
```python
action = np.array([0.5])   # 做多50%
action = np.array([-0.3])  # 做空30%（如果enable_shorting=True）
action = np.array([0.0])   # 平仓
```

#### 离散动作空间
```python
action = 0  # HOLD
action = 1  # BUY
action = 2  # SELL
```

### 1.5 实时数据更新

```python
# 从Kafka消费实时数据
new_price = 50000.0
new_volume = 1.5
new_orderbook = OrderBook(
    bids=[(49999, 1.0), (49998, 2.0)],
    asks=[(50001, 1.0), (50002, 2.0)]
)

env.update_market_data(new_price, new_volume, new_orderbook)
```

---

## 2. PPO/SAC训练器

### 2.1 PPO训练器

**优点**：稳定、易调参、适合离线训练

```python
from aetherlife.decision import PPOTrainer, TradingEnv

# 创建环境
env = TradingEnv(initial_balance=10000)

# 创建训练器
trainer = PPOTrainer(
    env=env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,
    tensorboard_log="./logs/ppo",
    verbose=1
)

# 训练
trainer.train(
    total_timesteps=100000,
    eval_env=eval_env,
    eval_freq=10000,
    n_eval_episodes=5
)

# 保存
trainer.save("./models/ppo_trading_agent.zip")
```

### 2.2 SAC训练器

**优点**：样本效率高、支持连续动作、适合在线学习

```python
from aetherlife.decision import SACTrainer

trainer = SACTrainer(
    env=env,
    learning_rate=3e-4,
    buffer_size=100000,
    batch_size=256,
    gamma=0.99,
    tau=0.005,
    ent_coef="auto",
    tensorboard_log="./logs/sac",
    verbose=1
)

trainer.train(total_timesteps=200000)
trainer.save("./models/sac_trading_agent.zip")
```

### 2.3 在线学习

```python
# 实盘交易中根据结果微调模型
obs = env.reset()
action = trainer.predict(obs, deterministic=True)

# 执行交易
real_reward, real_done = execute_trade_in_market(action)

# 在线学习
trainer.online_learn(obs, action, real_reward, real_done, n_steps=64)
```

### 2.4 多环境并行训练

```python
from aetherlife.decision import make_vec_env

# 创建8个并行环境
env = make_vec_env(
    env_fn=lambda: TradingEnv(initial_balance=10000),
    n_envs=8
)

trainer = PPOTrainer(env=env)
trainer.train(total_timesteps=500000)
```

---

## 3. 奖励函数塑形

### 3.1 基础奖励公式

```
reward = PnL% * 100 * 1.0
       + Sharpe * 2.0
       - MaxDD * 100
       - (TradeCost / Balance) * 50
       - (Slippage / Balance) * 80
       - ComplianceViolation * 500
```

### 3.2 使用RewardShaper

```python
from aetherlife.decision import RewardShaper, TradeMetrics

shaper = RewardShaper(
    pnl_weight=1.0,
    sharpe_weight=2.0,
    drawdown_penalty=100.0,
    cost_penalty=50.0,
    slippage_penalty=80.0,
    compliance_penalty=500.0
)

# 计算奖励
metrics = TradeMetrics(
    pnl_pct=0.02,
    sharpe_ratio=1.5,
    max_drawdown=0.03,
    trade_cost=2.0,
    slippage=1.0,
    balance=10000.0,
    is_violation=False
)

reward = shaper.shape_reward(metrics)
print(f"最终奖励: {reward:.2f}")
```

### 3.3 A股滑点预测

```python
from aetherlife.decision import StockConnectSlippagePredictor
from datetime import time

predictor = StockConnectSlippagePredictor()

# 预测滑点
slippage = predictor.predict_slippage(
    order_size=5000,                    # 5000 USD
    northbound_quota_remaining=45,      # 剩余45亿人民币
    current_time=time(9, 45),           # 开盘时段
    volatility=0.03,                    # 3%波动率
    symbol="600519"
)

print(f"预测滑点: {slippage:.4%}")  # 约 0.14%

# 更新历史数据（用于模型优化）
predictor.update_history(
    actual_slippage=0.0012,
    metadata={
        "order_size": 5000,
        "quota_remaining": 45,
        "time": time(9, 45),
        "symbol": "600519"
    }
)
```

### 3.4 合规检查

```python
from aetherlife.decision import ComplianceChecker

checker = ComplianceChecker()

# 执行所有检查
is_compliant, violations = checker.check_all(
    symbol="600519",
    current_time=time(10, 0),
    current_price=1850.0,
    prev_close=1800.0,
    order_size_usd=5000,
    quota_remaining_cny=80,
    current_drawdown=0.01
)

if not is_compliant:
    print("合规检查失败:")
    for violation in violations:
        print(f"  - {violation}")
```

---

## 4. 模型管理器

### 4.1 保存模型

```python
from aetherlife.decision import ModelManager

manager = ModelManager(models_dir="./models")

# 训练后保存
model_id = manager.save_model(
    trainer=trainer,
    version="1.0",
    performance_metrics={
        "sharpe_ratio": 1.8,
        "total_return": 0.25,
        "max_drawdown": -0.05,
        "win_rate": 0.58
    },
    description="PPO模型，训练10万步，Sharpe 1.8"
)

print(f"模型已保存: {model_id}")
# → ppo_v1.0_20250221_143020
```

### 4.2 加载模型

```python
# 加载指定模型
trainer = manager.load_model(model_id, env=env)

# 预测
obs = env.reset()
action = trainer.predict(obs, deterministic=True)
```

### 4.3 列出所有模型

```python
# 按Sharpe Ratio排序
models = manager.list_models(sort_by="sharpe_ratio")

for model in models:
    print(f"{model.model_id}:")
    print(f"  算法: {model.algorithm}")
    print(f"  版本: {model.version}")
    print(f"  Sharpe: {model.performance_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  回撤: {model.performance_metrics.get('max_drawdown', 0):.2%}")
```

### 4.4 获取最佳模型

```python
# 按Sharpe Ratio筛选最佳PPO模型
best_model = manager.get_best_model(
    metric="sharpe_ratio",
    algorithm="PPO"
)

if best_model:
    print(f"最佳模型: {best_model.model_id}")
    print(f"Sharpe: {best_model.performance_metrics['sharpe_ratio']:.2f}")
```

### 4.5 生产管理

```python
# 提升到生产环境
manager.promote_to_production(model_id)

# 查看当前生产模型
current_prod = manager.get_production_model()
print(f"生产模型: {current_prod}")

# 如果出问题，回滚
manager.rollback_production()
```

### 4.6 模型比较

```python
comparison = manager.compare_models(
    model_id1="ppo_v1.0_20250221",
    model_id2="ppo_v1.1_20250222"
)

for metric, data in comparison["metrics_comparison"].items():
    print(f"{metric}:")
    print(f"  模型1: {data['model1']:.4f}")
    print(f"  模型2: {data['model2']:.4f}")
    print(f"  提升: {data['improvement_pct']:.2f}%")
```

---

## 5. 命令行训练

### 5.1 基础训练

```bash
# 训练PPO（默认）
python scripts/train_rl_model.py --timesteps 100000

# 训练SAC
python scripts/train_rl_model.py --algorithm sac --timesteps 200000

# 带评估
python scripts/train_rl_model.py --timesteps 100000 --eval --eval-freq 10000
```

### 5.2 自定义参数

```bash
python scripts/train_rl_model.py \
  --algorithm ppo \
  --timesteps 500000 \
  --n-envs 8 \
  --learning-rate 1e-4 \
  --batch-size 128 \
  --initial-balance 10000 \
  --commission 0.001 \
  --slippage 0.0005 \
  --max-position 1.0 \
  --version "2.0" \
  --description "大批次训练，降低学习率"
```

### 5.3 查看训练进度

```bash
# 启动TensorBoard
tensorboard --logdir ./logs/tensorboard

# 浏览器打开 http://localhost:6006
```

---

## 6. 完整工作流

### 6.1 离线训练流程

```python
from aetherlife.decision import (
    TradingEnv, PPOTrainer, ModelManager, RewardShaper
)

# 1. 创建环境
env = TradingEnv(initial_balance=10000)

# 2. 创建训练器
trainer = PPOTrainer(
    env=env,
    learning_rate=3e-4,
    tensorboard_log="./logs/ppo"
)

# 3. 训练
trainer.train(total_timesteps=100000)

# 4. 保存
manager = ModelManager()
model_id = manager.save_model(
    trainer=trainer,
    version="1.0",
    performance_metrics={"sharpe_ratio": 1.5}
)

# 5. 提升到生产
manager.promote_to_production(model_id)
```

### 6.2 实盘在线学习流程

```python
# 1. 加载生产模型
manager = ModelManager()
prod_model_id = manager.get_production_model()
trainer = manager.load_model(prod_model_id, env=env)

# 2. 实盘交易循环
while True:
    # 获取市场数据
    market_data = fetch_market_data()
    env.update_market_data(market_data)
    
    # 预测动作
    obs = env.get_observation()
    action = trainer.predict(obs, deterministic=True)
    
    # 执行交易
    real_reward, real_done = execute_real_trade(action)
    
    # 在线学习（每小时微调一次）
    if should_online_learn():
        trainer.online_learn(obs, action, real_reward, real_done)
    
    # 每日评估，如果性能下降则回滚
    if should_daily_evaluate():
        current_sharpe = evaluate_model(trainer)
        if current_sharpe < threshold:
            manager.rollback_production()
```

---

## 7. 最佳实践

### 7.1 超参数调优

| 参数 | PPO推荐 | SAC推荐 | 说明 |
|------|---------|---------|------|
| learning_rate | 3e-4 | 3e-4 | 学习率 |
| batch_size | 64 | 256 | SAC需要更大批次 |
| gamma | 0.99 | 0.99 | 折扣因子 |
| buffer_size | - | 100000 | SAC的replay buffer |
| n_steps | 2048 | - | PPO每次更新收集的步数 |
| n_epochs | 10 | - | PPO每次更新的epoch数 |

### 7.2 奖励函数调优

- **高Sharpe为目标**：增大 `sharpe_weight`（如2.0→3.0）
- **控制回撤**：增大 `drawdown_penalty`（如100→200）
- **减少交易频率**：增大 `cost_penalty`（如50→100）
- **A股滑点敏感**：增大 `slippage_penalty`（如80→150）

### 7.3 训练技巧

1. **从小规模开始**：先训练1万步快速验证，再扩展到10万、100万
2. **使用评估环境**：定期在未见过的数据上评估，避免过拟合
3. **多环境并行**：PPO建议4-8个并行环境，加速训练
4. **在线学习谨慎**：实盘微调步数不宜过大（64-128步），避免遗忘历史经验
5. **定期回测**：每周在最新历史数据上回测，检测模型退化

### 7.4 生产部署

1. **A/B测试**：新模型先在小仓位测试（10%资金），验证后再全量
2. **自动回滚**：设置性能阈值（如Sharpe < 1.0），自动回滚到previous_model
3. **版本管理**：每次重要更新递增版本号（1.0 → 1.1）
4. **性能监控**：实时追踪Sharpe、回撤、胜率，异常时触发告警

---

## 8. 故障排查

### 8.1 训练不收敛

**现象**：奖励值始终在0附近波动，不增长

**可能原因**：
- 奖励函数设计问题（惩罚过重）
- 学习率过高或过低
- 状态空间归一化问题

**解决方案**：
```python
# 1. 降低惩罚系数
shaper = RewardShaper(
    drawdown_penalty=50,  # 从100降到50
    cost_penalty=25       # 从50降到25
)

# 2. 调整学习率
trainer = PPOTrainer(env=env, learning_rate=1e-4)  # 从3e-4降到1e-4

# 3. 检查状态归一化
env = TradingEnv()
obs = env.reset()
print(obs)  # 确保值在[-10, 10]范围内
```

### 8.2 过拟合

**现象**：训练集表现好，评估集表现差

**解决方案**：
```python
# 1. 增加正则化（熵系数）
trainer = PPOTrainer(env=env, ent_coef=0.05)  # 从0.01增加到0.05

# 2. 使用更多样化的训练数据
# 3. 定期在评估环境上验证
trainer.train(total_timesteps=100000, eval_freq=5000)
```

### 8.3 在线学习退化

**现象**：实盘运行一段时间后性能下降

**解决方案**：
```python
# 1. 减少在线学习步数
trainer.online_learn(obs, action, reward, done, n_steps=32)  # 从64降到32

# 2. 定期回滚
if daily_sharpe < 0.5:
    manager.rollback_production()

# 3. 混合训练（在线 + 历史数据）
# 每晚重新在历史数据上训练，然后在线微调
```

---

## 9. 性能指标

### 9.1 关键指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| Sharpe Ratio | > 1.5 | 风险调整后收益 |
| Max Drawdown | < 10% | 最大回撤 |
| Win Rate | > 55% | 胜率 |
| Profit Factor | > 1.5 | 盈亏比 |
| Total Return | > 20%/年 | 年化收益 |

### 9.2 计算示例

```python
from aetherlife.decision import RewardShaper

shaper = RewardShaper()

# 计算Sharpe Ratio
returns = [0.01, -0.005, 0.02, 0.015, -0.01, ...]
sharpe = shaper.calculate_sharpe_ratio(returns, risk_free_rate=0.03)
print(f"Sharpe Ratio: {sharpe:.2f}")

# 计算最大回撤
equity_curve = [10000, 10100, 10050, 10200, 10150, ...]
max_dd = shaper.calculate_max_drawdown(equity_curve)
print(f"最大回撤: {max_dd:.2%}")
```

---

## 10. 下一步

- **阶段4**：执行层优化（Rust引擎、智能路由）
- **阶段5**：进化层实现（LLM策略生成、热更新）
- **阶段6**：守护层与部署（VaR、监控、K8s）

**立即行动**：
```bash
# 1. 训练第一个模型
python scripts/train_rl_model.py --timesteps 50000 --eval

# 2. 查看TensorBoard
tensorboard --logdir ./logs/tensorboard

# 3. 回测验证（下一阶段实现）
```
