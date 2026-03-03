# AetherLife 市场支持完整说明

## 📊 当前支持状态

### ✅ 已完成并可立即使用

#### 1. 加密货币市场（Production Ready）
**支持交易所**：
- Binance（现货、合约、永续）
- Bybit（现货、合约、永续）
- OKX（现货、合约、永续）

**特点**：
- ✅ WebSocket实时行情
- ✅ REST API下单
- ✅ 杠杆1-125倍
- ✅ 完整风控体系

**配置示例**：
```json
{
  "exchange": "binance",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "leverage": 20,
  "testnet": true
}
```

---

### ⚠️ 框架已完成，需要IBKR账户激活

#### 2. A股市场（Stock Connect）
**接入方式**：IBKR TWS + Stock Connect

**特色功能**：
- ✅ 涨跌停检测（主板±10%，科创板±20%）
- ✅ 北向额度实时监控
- ✅ 交易时段限制（09:30-11:30, 13:00-15:00）
- ✅ 印花税成本计算（卖出0.1%）
- ✅ T+1交易规则

**代码示例**：
```python
from aetherlife.perception import IBKREnhancedConnector

connector = await create_ibkr_enhanced_connector()
# 订阅A股（通过港交所）
await connector.subscribe_ticker(
    symbol="600000",  # 浦发银行
    exchange="SEHK",
    currency="HKD"
)
```

#### 3. 港股市场
**接入方式**：IBKR TWS直接接入

**特点**：
- ✅ T+0交易
- ✅ 无涨跌停限制
- ✅ 印花税0.13%（卖出）

#### 4. 美股市场
**接入方式**：IBKR TWS直接接入

**支持产品**：
- ✅ 股票
- ✅ ETF
- ✅ 期权（预留接口）

#### 5. 外汇市场
**接入方式**：IBKR FX接口

**支持货币对**：
- EUR/USD, GBP/USD, USD/JPY
- AUD/USD, NZD/USD, USD/CAD
- USD/CHF

#### 6. 期货市场
**接入方式**：IBKR期货接口

**支持品种**：
- 股指期货：ES, NQ, YM, RTY
- 商品期货：CL（原油）, GC（黄金）, SI（白银）
- 国债期货：ZN, ZF, ZT

---

## 🔧 技术实现

### 核心组件

#### 1. IBKR连接器增强版
文件：`src/aetherlife/perception/ibkr_connector_enhanced.py`

**功能**：
- ✅ 统一合约创建（股票/期货/外汇）
- ✅ 实时行情订阅
- ✅ 订单执行
- ✅ 账户管理
- ✅ 持仓查询
- ✅ 北向额度查询
- ✅ 自动断线重连

#### 2. 市场配置文件
文件：`configs/market_support.json`

**内容**：
- 各市场详细配置
- 产品列表
- 风险参数
- 使用示例

#### 3. 专业化Agent
文件：`src/aetherlife/cognition/agent_specialized.py`

**包含**：
- ChinaAStockAgent（A股专家）
- GlobalStockAgent（美股/港股专家）
- CryptoNanoAgent（加密货币专家）
- ForexMicroAgent（外汇专家）
- FuturesMicroAgent（期货专家）

---

## 🚀 使用指南

### 1. 加密货币交易（推荐新手开始）

```bash
# 安装依赖
pip install -r requirements.txt

# 配置API密钥
cp .env.example .env
# 编辑 .env 文件填入交易所API

# 启动交易机器人
python src/trading_bot.py --exchange binance --symbols BTCUSDT --strategy rsi
```

### 2. 股票/外汇/期货交易

**前置要求**：
1. 申请IBKR账户（盈透证券）
2. 下载并安装TWS或IB Gateway
3. 在TWS中启用API访问

**启动步骤**：
```bash
# 启动TWS/Gateway（确保API端口开放）

# 运行IBKR连接器演示
python -m aetherlife.perception.ibkr_connector_enhanced

# 或集成到交易系统
python src/trading_bot.py --exchange ibkr --symbols AAPL --market us_stock
```

---

## 📋 配置参数

### IBKR配置
```json
{
  "ibkr": {
    "host": "127.0.0.1",
    "port": 7497,        // Paper trading
    "client_id": 1,
    "readonly": false    // 交易需设为false
  }
}
```

### 市场特定配置
```json
{
  "risk_management": {
    "a_stock": {
      "max_position_size": 0.1,     // 最大仓位10%
      "stop_loss_pct": 0.05,        // 止损5%
      "take_profit_pct": 0.1,       // 止盈10%
      "northbound_quota_threshold": 0.1  // 北向额度预警10%
    },
    "crypto": {
      "max_leverage": 20,           // 最大杠杆20倍
      "stop_loss_pct": 0.1,
      "take_profit_pct": 0.2
    }
  }
}
```

---

## 🛡️ 风险控制

### A股特殊风控
- **涨跌停保护**：接近涨跌停时自动暂停交易
- **额度监控**：北向额度不足时发出警告
- **时段限制**：非交易时段拒绝下单
- **成本计算**：自动计算印花税等交易成本

### 通用风控
- **最大仓位限制**
- **止损止盈机制**
- **账户资金监控**
- **异常波动检测**

---

## 📚 相关文档

- [感知层升级指南](docs/PERCEPTION_UPGRADE_GUIDE.md) - IBKR详细使用
- [快速开始指南](docs/QUICK_START.md) - 系统入门
- [部署指南](docs/DEPLOYMENT_GUIDE.md) - 生产环境部署
- [最终交付总结](docs/FINAL_SUMMARY.md) - 系统完整功能

---

## 🆘 支持与帮助

遇到问题？
1. 查看[故障排查文档](docs/TROUBLESHOOTING.md)
2. 检查[TWS API文档](https://interactivebrokers.github.io/tws-api/)
3. 提交GitHub Issue

---

**状态更新**：2025年2月21日  
所有市场框架已完成，加密货币可立即使用，股票等市场需IBKR账户激活。
