# AetherLife 与 IBKR 完全对接指南

## 🎯 对接目标

将 AetherLife 量化交易系统完全对接到 IBKR TWS/Gateway，实现：
- ✅ 多市场统一接入（A股/港股/美股/外汇/期货）
- ✅ 智能订单路由
- ✅ 实时行情订阅
- ✅ 自动化订单执行
- ✅ 账户与持仓管理
- ✅ 风险控制

---

## 🏗️ 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   感知层         │    │   认知层          │    │   执行层         │
│                 │    │                  │    │                 │
│ IBKR连接器      │───▶│ 智能路由器        │───▶│ IBKR执行器       │
│ - 行情订阅       │    │ - 市场选择        │    │ - 订单执行       │
│ - 合约管理       │    │ - 订单类型选择     │    │ - 账户管理       │
│ - 额度查询       │    │ - 成本估算        │    │ - 持仓查询       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## 📦 核心组件

### 1. IBKR增强连接器
**文件**: `src/aetherlife/perception/ibkr_connector_enhanced.py`

**功能**:
- 统一合约创建（股票/期货/外汇）
- 实时行情订阅与推送
- A股Stock Connect特殊处理
- 北向额度查询
- 自动断线重连

### 2. IBKR执行器
**文件**: `src/aetherlife/execution/ibkr_executor.py`

**功能**:
- 订单执行（市价单/限价单）
- 账户信息查询
- 持仓管理
- 订单状态跟踪
- 成交回报处理

### 3. 智能路由器
**文件**: `src/aetherlife/execution/smart_router.py`

**功能**:
- 市场类型识别与交易所选择
- 订单类型智能匹配
- 流动性评估
- 成本估算（滑点+手续费）

---

## 🔧 安装与配置

### 1. 安装依赖
```bash
pip install ib_insync
```

### 2. 配置IBKR TWS
1. 下载并安装 [IBKR TWS](https://www.interactivebrokers.com/en/index.php?f=16047) 或 IB Gateway
2. 启用API访问：
   - Edit → Global Configuration → API → Settings
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost only
   - Socket Port: `7497` (Paper Trading)
3. 启动TWS/Gateway

### 3. 系统配置
**文件**: `configs/ibkr_integration.json`

```json
{
  "ibkr_integration": {
    "connection": {
      "host": "127.0.0.1",
      "paper_trading_port": 7497,
      "live_trading_port": 7496,
      "client_id": 1
    }
  }
}
```

---

## 🚀 使用示例

### 1. 运行对接演示
```bash
python scripts/ibkr_full_integration_demo.py
```

### 2. 基本用法
```python
import asyncio
from aetherlife.perception.ibkr_connector_enhanced import create_ibkr_enhanced_connector
from aetherlife.execution.ibkr_executor import create_ibkr_executor

async def main():
    # 1. 创建连接器
    connector = await create_ibkr_enhanced_connector()
    
    # 2. 创建执行器
    executor = await create_ibkr_executor()
    
    # 3. 订阅行情
    await connector.subscribe_ticker("AAPL", callback=lambda d: print(d['last_price']))
    
    # 4. 下单
    result = await executor.place_order(
        symbol="AAPL",
        action="BUY",
        quantity=10,
        order_type="MKT"
    )
    
    print(f"订单ID: {result['order_id']}")
    
    # 5. 查询账户
    account = await executor.get_account_summary()
    print(f"可用资金: ${account['available_funds']}")
    
    # 6. 清理
    await connector.close()
    await executor.close()

asyncio.run(main())
```

### 3. 智能路由使用
```python
from aetherlife.execution.smart_router import SmartRouter
from aetherlife.cognition.schemas import TradeIntent, Action, Market

# 创建路由器
router = SmartRouter()

# 创建交易意图
intent = TradeIntent(
    action=Action.BUY,
    market=Market.A_STOCK,  # 或 Market.US_STOCK, Market.CRYPTO 等
    symbol="600000",
    quantity_pct=0.1,
    confidence=0.8
)

# 路由决策
decision = router.route(intent, balance=10000)

print(f"交易所: {decision.exchange}")
print(f"订单类型: {decision.order_type}")
print(f"预估成本: ${decision.estimated_total_cost}")
```

---

## 📊 支持的市场

| 市场 | 证券类型 | 接入方式 | 状态 |
|------|----------|----------|------|
| A股 | 股票 | IBKR Stock Connect | ✅ 完成 |
| 港股 | 股票 | IBKR直接接入 | ✅ 完成 |
| 美股 | 股票/ETF | IBKR直接接入 | ✅ 完成 |
| 外汇 | 货币对 | IBKR FX | ✅ 完成 |
| 期货 | 股指/商品 | IBKR期货 | ✅ 完成 |

---

## ⚙️ 高级配置

### A股特殊配置
```json
{
  "market_specific": {
    "a_stock": {
      "trading_hours": [
        {"start": "09:30", "end": "11:30"},
        {"start": "13:00", "end": "15:00"}
      ],
      "limit_threshold": 0.1,      // ±10%涨跌停
      "stamp_duty_rate": 0.001     // 卖出印花税0.1%
    }
  }
}
```

### 风险管理配置
```json
{
  "risk_management": {
    "ibkr": {
      "max_position_size": 0.1,    // 最大仓位10%
      "stop_loss_pct": 0.05,       // 止损5%
      "take_profit_pct": 0.1,      // 止盈10%
      "northbound_quota_warning": 0.1  // 北向额度预警10%
    }
  }
}
```

---

## 🛡️ 风险控制

### 1. A股风控机制
- **涨跌停保护**：接近涨跌停时暂停交易
- **额度监控**：北向额度不足时预警
- **时段限制**：非交易时段拒绝下单
- **成本计算**：自动计算印花税等费用

### 2. 通用风控
- 最大仓位限制
- 止损止盈机制
- 账户资金监控
- 异常波动检测

---

## 📈 性能监控

### 关键指标
- 订单执行延迟
- 连接稳定性
- 行情更新频率
- 账户资金变动

### 日志配置
```python
import logging
logging.basicConfig(level=logging.INFO)
```

---

## 🐛 故障排查

### 常见问题

1. **连接失败**
   ```
   错误: ConnectionRefusedError
   解决: 检查TWS是否启动，端口是否正确
   ```

2. **合约无效**
   ```
   错误: ValueError: 合约无效
   解决: 检查证券代码和交易所设置
   ```

3. **权限不足**
   ```
   错误: 订单被拒绝
   解决: 确认TWS中启用了交易权限
   ```

---

## 📚 相关文档

- [市场支持说明](MARKET_SUPPORT.md)
- [感知层升级指南](PERCEPTION_UPGRADE_GUIDE.md)
- [执行层设计文档](EXECUTION_LAYER_DESIGN.md)
- [风险管理手册](RISK_MANAGEMENT.md)

---

## 🆘 技术支持

如有问题，请：
1. 查看日志文件
2. 参考IBKR官方文档
3. 提交GitHub Issue

---
**版本**: v1.0.3  
**更新时间**: 2025年2月21日
