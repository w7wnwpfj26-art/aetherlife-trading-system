# 🚀 AetherLife 部署速查卡

## 📦 一键启动（本地Docker）

```bash
# 1. 配置环境
cp .env.example .env
vim .env  # 添加API密钥

# 2. 启动
docker-compose up -d

# 3. 访问
# Admin UI: http://localhost:18789
# Grafana:  http://localhost:3000 (admin/aether_admin)
# Prometheus: http://localhost:9090
```

## ☸️ K8s生产部署

```bash
# 1. 创建Secret
kubectl create secret generic aetherlife-secrets \
  --from-env-file=.env -n aetherlife

# 2. 部署
kubectl apply -f k8s/deployment.yaml

# 3. 查看状态
kubectl get pods -n aetherlife
```

## 🔑 必需的环境变量

```bash
# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=7497

# 加密货币
BINANCE_API_KEY=...
BINANCE_SECRET=...
```

## 📊 核心端口

| 服务 | 端口 | 用途 |
|------|------|------|
| AetherLife Core | 8000 | 主应用 |
| Admin UI | 18789 | 管理界面 |
| Grafana | 3000 | 监控可视化 |
| Prometheus | 9090 | 指标收集 |
| Redis | 6379 | 缓存/向量存储 |
| ClickHouse | 8123/9000 | 时序数据库 |
| Kafka | 9092 | 消息队列 |

## 🛠️ 常用命令

```bash
# Docker
docker-compose logs -f aetherlife     # 查看日志
docker-compose restart aetherlife     # 重启
docker-compose down -v                # 清除数据

# K8s
kubectl logs -f deployment/aetherlife-core -n aetherlife  # 日志
kubectl scale deployment aetherlife-core --replicas=5 -n aetherlife  # 扩容
kubectl rollout restart deployment/aetherlife-core -n aetherlife  # 重启
```

## 📈 核心指标

- `aetherlife_portfolio_total_value` - 总资产
- `aetherlife_sharpe_ratio_7d` - 7日夏普
- `aetherlife_max_drawdown` - 最大回撤
- `aetherlife_var_1day_95` - 1日95% VaR

## 🆘 故障排除

```bash
# 健康检查
curl http://localhost:8000/health

# Redis连接测试
docker exec -it aetherlife_redis redis-cli ping

# 查看Kafka Topics
docker exec -it aetherlife_kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# 内存使用
kubectl top pods -n aetherlife
```

## 📚 完整文档

- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [快速开始](docs/QUICK_START.md)
- [最终总结](docs/FINAL_SUMMARY.md)
