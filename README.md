# AetherLife Trading System

**版本**: v1.0.1 (2025-02-21) | [English](README_EN.md) | [文档](docs/)

基于Python的AI驱动多市场量化交易系统，支持加密货币、A股、美股、期货、外汇等多市场交易。

## 🎉 最新更新 (v1.0.1)

- ✅ **完整订单管理系统**（修复残缺模块）
- ✅ **性能优化**：内存队列 O(n)→O(1)
- ✅ **日志持久化** + 动态级别调整
- ✅ **指数退避重试**策略
- ✅ **真实网络连接测试**

详见: [优化汇总文档](docs/OPTIMIZATION_SUMMARY.md)

> ⚠️ **风险提示**: 高杠杆交易风险极高，可能亏光全部本金。本项目仅供学习研究，不构成投资建议。

## 📁 项目结构

```
合约交易系统/
├── README.md
├── config.json
├── requirements.txt
├── src/
│   ├── trading_bot.py           # 主程序
│   ├── data/
│   │   └── data_fetcher.py     # 数据获取
│   ├── strategies/
│   │   └── strategy.py         # 策略模块
│   ├── execution/
│   │   └── exchange_client.py  # 交易所API
│   └── utils/
│       ├── risk_manager.py     # 风控模块
│       └── ai_enhancer.py      # AI 增强模块 ⭐
├── tests/
└── docs/
```

## 🚀 快速开始

```bash
cd 合约交易系统
pip install -r requirements.txt
python src/trading_bot.py
```

---

## 🤖 AI 增强功能 (新增)

### 1. 多Agent协调器 (MultiAgentCoordinator)
参考 Gigabrain，7个AI Agent分工协作：

| Agent | 功能 | 权重 |
|-------|------|------|
| microstructure | 订单簿分析 | 15% |
| technical | 技术分析 | 25% |
| fundamental | 基本面分析 | 15% |
| sentiment | 情绪分析 | 15% |
| onchain | 链上数据 | 10% |
| news | 新闻分析 | 10% |
| social | 社交媒体 | 10% |

### 2. 机器学习预测器 (ML Predictor)
基于 FreqAI 思路：
- 自动特征工程
- 实时模型训练
- 自适应市场变化

### 3. 情绪分析器 (SentimentAnalyzer)
- Twitter 情绪监控
- 恐慌/贪婪指数
- 新闻情感分析

### 4. 自动复利管理器 (AutoCompoundManager)
Web4.0 思路：
- 利润自动复投
- 仓位再平衡
- 资金效率最大化

## 📊 系统架构 (AI增强版)

```
┌─────────────────────────────────────────────────────────┐
│                    AI 增强层                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │多Agent协作  │ │ML预测器     │ │情绪分析    │      │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘      │
│         │               │               │              │
│         └───────────────┼───────────────┘              │
│                         ↓                             │
│              ┌──────────────────┐                     │
│              │  综合决策引擎    │                     │
│              └────────┬─────────┘                     │
└───────────────────────┼────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                   基础层 (原有)                         │
│  数据层 → 策略层 → 风控层 → 执行层                    │
└─────────────────────────────────────────────────────────┘
```

## ⚙️ 配置示例

```json
{
    "exchange": "binance",
    "testnet": true,
    "ai_enhance": {
        "enabled": true,
        "multi_agent": true,
        "ml_predictor": true,
        "sentiment": true,
        "auto_compound": true
    },
    "risk": {
        "max_position_pct": 0.1,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05
    }
}
```

## 🎯 策略建议

| 市场环境 | 推荐策略 |
|----------|----------|
| 趋势明显 | 突破 + ML预测 |
| 震荡整理 | 网格 + 情绪分析 |
| 波动剧烈 | 多Agent协作 + 严格风控 |
| 数据驱动 | ML自适应策略 |

## ⚠️ 重要警告

1. **先用模拟盘测试**: 建议先在测试网运行至少1个月
2. **AI不是万能的**: 市场有风险，AI也会亏损
3. **设置止损**: 永远设置止损，不要扛单
4. **不要杠杆太高**: 建议不超过10x

## 📝 开发日志

### 2026-02-20
- 项目初始化
- 完成数据层、策略层、执行层、风控层
- **新增 AI 增强模块**
  - 多Agent协调器
  - 机器学习预测器
  - 情绪分析器
  - 自动复利管理器

## 🔗 参考

- [Freqtrade](https://github.com/freqtrade/freqtrade) - ML交易
- [Gigabrain](https://gigabrain.ai) - 多Agent交易
- [Conway](https://conway.tech) - Web4.0 自主交易
