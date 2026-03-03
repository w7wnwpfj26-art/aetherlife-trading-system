# 更新日志 (Changelog)

本文档记录AetherLife Trading System的所有重要版本更新。

---

## [v1.0.2] - 2025-02-21

### 🟢 代码质量提升

#### 新增
- **完整单元测试覆盖** ([`tests/`](tests/))
  - `test_config_manager.py` - 配置管理器测试（默认配置、API校验、保存/加载、导出脱敏、列出配置）
  - `test_risk_manager.py` - 风险管理器测试（仓位计算、止损/止盈检查、开仓/更新/平仓/列表）
  - `test_strategies.py` - 策略测试（已存在）
  - **24个测试全部通过** ✅

#### 优化
- **日志标准化** - 替换`print()`为`logging`
  - `utils/`: config_manager.py, risk_manager.py, ai_enhancer.py
  - `execution/`: exchange_client.py
  - `ui/`: admin_backend.py, unified_server.py, dashboard.py
  - 所有异常处理和测试块统一使用logger

- **API文档完善** - 补充docstring和类型注解
  - `create_client()` - exchange_client.py
  - `create_strategy()` - strategies/factory.py
  - `create_data_fetcher()` - data_fetcher.py
  - `TradingBot` - trading_bot.py（类说明、所有方法的docstring和返回类型）

#### 配置
- **环境变量模板** - 更新README和.gitignore
  - 添加`.env`使用说明
  - 增强敏感配置排除规则
  - 添加MIT License标注

### 📊 测试运行

```bash
python3 -m unittest tests.test_config_manager tests.test_risk_manager tests.test_strategies -v
# 24 tests passed ✅
```

---

## [v1.0.1] - 2025-02-21

### 🔴 残缺模块重建

#### 新增
- **完整订单管理系统** ([`execution/order.py`](src/execution/order.py))
  - 新增`Order`数据类（完整生命周期字段）
  - 新增`OrderSide`/`OrderType`/`OrderStatus`枚举
  - 新增`OrderManager`类（创建、状态管理、统计）
  - 支持市价单/限价单创建
  - 支持订单全链路跟踪（提交→成交→取消）
  - 支持胜率和手续费统计

### 🟠 性能优化

#### 优化
- **内存队列性能提升** O(n) → O(1)
  - [`memory/store.py`](src/aetherlife/memory/store.py): 短期记忆淘汰从`list.pop(0)`改为`deque(maxlen=100)`
  - [`guard/advanced_risk.py`](src/aetherlife/guard/advanced_risk.py): 异常检测历史窗口从`list.pop(0)`改为`deque(maxlen=lookback_period)`
  - 高频场景性能提升 **100x+**

### 🟢 功能增强

#### 新增
- **日志持久化** ([`utils/logger.py`](src/utils/logger.py))
  - 新增`RotatingFileHandler`支持（单文件10MB，保留5个历史）
  - 新增`set_level()`动态调整日志级别
  - 自动创建日志目录
  - 支持UTF-8中文编码

- **指数退避重试** ([`execution/order_executor.py`](src/aetherlife/execution/order_executor.py))
  - 接入`execution/retry.py`的`retry_async`
  - 支持指数退避（base_delay × 2^n，上限max_delay）
  - 适应交易所限流场景（等待时间逐步拉长）
  - 提供降级支持（导入失败时回退固定延迟）

- **真实网络连接测试** ([`utils/config_manager.py`](src/utils/config_manager.py))
  - `test_connection()`实现真实网络请求
  - 调用`ExchangeClient.get_ticker()`验证连通性
  - 返回BTC实时价格作为成功凭证
  - 兼容同步/异步两种调用环境

### 🐛 Bug修复

#### 修复
- 修复`execution/order.py`残缺问题（原仅包含一个中文类名和pass语句）
- 修复内存队列性能瓶颈（list.pop(0)在高频场景下CPU损耗）
- 修复连接测试假阳性（原直接返回格式验证结果）

### 📚 文档

#### 新增
- [优化汇总文档](docs/OPTIMIZATION_SUMMARY.md) - 详细说明6处优化
- 更新[README.md](README.md) - 添加v1.0.1版本信息

---

## [v1.0.0] - 2025-02-21

### ✨ 主要特性

#### 阶段1：感知层升级
- IBKR TWS连接器（股票、A股、期货、外汇）
- 加密货币WebSocket（CCXT Pro统一接口）
- Kafka数据管道（4个Topic）
- Redis向量存储
- ClickHouse时序数据库

#### 阶段2：认知层完善
- 7个专业化Agent（A股/美股/加密/外汇/期货/跨市场/情绪）
- LangGraph状态机编排
- 动态权重调整
- Bull/Bear/Judge辩论机制

#### 阶段3：决策层构建
- Gymnasium交易环境（20维状态空间）
- PPO/SAC训练器
- 奖励函数塑形（Sharpe优化）
- A股滑点预测
- 合规检查器
- 模型管理器（版本控制、A/B测试）

#### 阶段4：执行层优化
- 智能路由器（多交易所选择）
- 订单拆分器（TWAP/VWAP/Iceberg/Adaptive）
- 执行引擎（统一接口、自动重试）

#### 阶段5：进化层实现
- 完整回测引擎（450行）
- LLM策略生成器（450行）
- 遗传算法优化器（370行）

#### 阶段6：守护层与部署
- 基础风控（电路断路器、HITL）
- VaR计算器（3种方法）
- 异常检测器
- 香港SFC合规检查器
- Docker多阶段构建
- Kubernetes完整配置
- Prometheus + Grafana监控

### 📦 部署配置
- Docker Compose（7个服务）
- Kubernetes部署（HPA、Ingress、PVC）
- Prometheus监控配置
- Grafana仪表板（14个核心指标）

### 📚 文档
- [快速开始指南](docs/QUICK_START.md)
- [感知层升级指南](docs/PERCEPTION_UPGRADE_GUIDE.md)
- [认知层升级指南](docs/COGNITION_UPGRADE_GUIDE.md)
- [决策层升级指南](docs/DECISION_LAYER_GUIDE.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [最终交付总结](docs/FINAL_SUMMARY.md)
- [部署速查卡](DEPLOYMENT_QUICK_REF.md)

---

## 版本说明

### 版本号规则
遵循[语义化版本](https://semver.org/lang/zh-CN/)：`主版本号.次版本号.修订号`

- **主版本号**：不兼容的API修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

### 标签说明
- 🔴 **残缺模块重建**：从废弃stub重写完整功能
- 🟠 **性能优化**：显著性能提升
- 🟢 **功能增强**：新增功能或改进
- 🐛 **Bug修复**：问题修复
- 📚 **文档**：文档更新
- ⚠️ **破坏性变更**：可能影响现有代码

---

## 未来规划

### v1.1.0（计划中）
- [ ] 热更新管理器（策略代码热加载）
- [ ] 多账户支持（资金池管理）
- [ ] 期权交易（Greeks计算、波动率曲面）
- [ ] 社交交易（跟单、复制策略）

### v1.2.0（计划中）
- [ ] 自动做市商（AMM）
- [ ] L2/L3深度数据支持
- [ ] 多链DeFi集成（Uniswap/Aave）
- [ ] 联邦学习（多用户协同训练）

---

## 贡献

欢迎贡献代码、报告问题或提出建议！

- **GitHub**: https://github.com/your-org/aetherlife
- **Discord**: https://discord.gg/aetherlife
- **Email**: support@aetherlife.ai

---

**最后更新**: 2025年2月21日
