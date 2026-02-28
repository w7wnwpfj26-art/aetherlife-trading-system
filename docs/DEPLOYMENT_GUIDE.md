# AetherLife 部署指南

本指南提供AetherLife交易系统的完整部署方案，包括Docker、Kubernetes和生产环境最佳实践。

---

## 📋 目录

- [前置要求](#前置要求)
- [本地Docker部署](#本地docker部署)
- [Kubernetes生产部署](#kubernetes生产部署)
- [监控配置](#监控配置)
- [安全加固](#安全加固)
- [故障排除](#故障排除)

---

## 🔧 前置要求

### 硬件要求

**最小配置（开发/测试）：**
- CPU: 4核
- 内存: 8GB
- 存储: 50GB SSD

**推荐配置（生产）：**
- CPU: 16核
- 内存: 32GB
- 存储: 500GB NVMe SSD
- 网络: 1Gbps+

### 软件要求

```bash
# Docker环境
Docker >= 20.10
Docker Compose >= 2.0

# Kubernetes环境
Kubernetes >= 1.28
kubectl >= 1.28
Helm >= 3.10
```

---

## 🐳 本地Docker部署

### 1. 克隆仓库并配置

```bash
# 克隆项目
git clone https://github.com/your-org/aetherlife.git
cd aetherlife

# 复制配置文件
cp .env.example .env

# 编辑配置（添加API密钥等）
vim .env
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# LLM API
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# 加密货币交易所
BINANCE_API_KEY=your-binance-api-key
BINANCE_SECRET=your-binance-secret
BYBIT_API_KEY=your-bybit-api-key
BYBIT_SECRET=your-bybit-secret

# 数据库
REDIS_URL=redis://redis:6379/0
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_USER=aether
CLICKHOUSE_PASSWORD=aether_password

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f aetherlife
```

### 4. 验证部署

```bash
# 检查健康状态
curl http://localhost:8000/health

# 访问Admin UI
open http://localhost:18789

# 访问Grafana
open http://localhost:3000
# 默认账号: admin / aether_admin

# 访问Prometheus
open http://localhost:9090
```

### 5. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（谨慎使用！）
docker-compose down -v
```

---

## ☸️ Kubernetes生产部署

### 1. 准备Kubernetes集群

```bash
# 验证集群连接
kubectl cluster-info

# 创建命名空间
kubectl apply -f k8s/deployment.yaml
```

### 2. 配置Secrets

```bash
# 创建API密钥Secret
kubectl create secret generic aetherlife-secrets \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=IBKR_USERNAME=your-username \
  --from-literal=IBKR_PASSWORD=your-password \
  --from-literal=BINANCE_API_KEY=your-key \
  --from-literal=BINANCE_SECRET=your-secret \
  -n aetherlife

# 或从文件创建
kubectl create secret generic aetherlife-secrets \
  --from-env-file=.env \
  -n aetherlife
```

### 3. 部署应用

```bash
# 应用所有配置
kubectl apply -f k8s/

# 查看部署状态
kubectl get pods -n aetherlife
kubectl get svc -n aetherlife

# 查看详细信息
kubectl describe deployment aetherlife-core -n aetherlife
```

### 4. 配置持久化存储

确保创建了PersistentVolume（PV）：

```yaml
# 示例：使用本地存储（生产环境建议使用云存储）
apiVersion: v1
kind: PersistentVolume
metadata:
  name: aetherlife-logs-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
  - ReadWriteMany
  hostPath:
    path: "/mnt/aetherlife/logs"
```

### 5. 配置Ingress（可选）

```bash
# 安装Nginx Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace

# 配置TLS证书（使用cert-manager）
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true

# 应用Ingress配置
kubectl apply -f k8s/deployment.yaml
```

### 6. 扩缩容

```bash
# 手动扩容
kubectl scale deployment aetherlife-core --replicas=5 -n aetherlife

# 查看HPA状态
kubectl get hpa -n aetherlife

# HPA会根据CPU/内存自动扩缩容
# 配置: minReplicas=2, maxReplicas=10
```

---

## 📊 监控配置

### Prometheus + Grafana

#### 1. 访问Grafana

```bash
# 本地端口转发
kubectl port-forward svc/grafana 3000:3000 -n aetherlife

# 打开浏览器
open http://localhost:3000
```

#### 2. 导入仪表板

1. 登录Grafana（admin / aether_admin）
2. 导航至 **Dashboards → Import**
3. 上传 `configs/grafana/dashboards/aetherlife-core.json`

#### 3. 核心监控指标

| 指标名称 | 说明 |
|---------|------|
| `aetherlife_portfolio_total_value` | 总资产净值 |
| `aetherlife_portfolio_daily_return` | 今日收益率 |
| `aetherlife_sharpe_ratio_7d` | 7日夏普比率 |
| `aetherlife_max_drawdown` | 最大回撤 |
| `aetherlife_var_1day_95` | 1日95% VaR |
| `aetherlife_active_orders` | 活跃订单数 |
| `aetherlife_trades_total` | 总交易次数 |
| `aetherlife_agent_weight` | Agent决策权重 |

#### 4. 配置告警

编辑 `configs/prometheus/rules/alerts.yml`:

```yaml
groups:
- name: aetherlife_alerts
  rules:
  # 高回撤告警
  - alert: HighDrawdown
    expr: aetherlife_max_drawdown < -0.20
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "回撤超过20%"
      description: "当前回撤: {{ $value | humanizePercentage }}"

  # 系统离线告警
  - alert: SystemDown
    expr: up{job="aetherlife_core"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "AetherLife系统离线"
```

---

## 🔒 安全加固

### 1. 网络隔离

```bash
# 创建网络策略（限制Pod间通信）
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: aetherlife-network-policy
  namespace: aetherlife
spec:
  podSelector:
    matchLabels:
      app: aetherlife
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: aetherlife
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          component: redis
    ports:
    - protocol: TCP
      port: 6379
EOF
```

### 2. Secret加密

```bash
# 启用etcd加密（Kubernetes层面）
# 参考官方文档: https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/

# 使用Sealed Secrets（推荐）
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml
```

### 3. RBAC权限控制

```yaml
# 创建ServiceAccount和Role
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aetherlife-sa
  namespace: aetherlife
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aetherlife-role
  namespace: aetherlife
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
```

### 4. 容器安全

- ✅ 使用非root用户运行（已配置: `USER aether`）
- ✅ 最小化镜像体积（多阶段构建）
- ✅ 定期更新依赖
- ✅ 扫描镜像漏洞（使用Trivy）

```bash
# 安装Trivy
brew install trivy

# 扫描镜像
trivy image aetherlife:latest
```

---

## 🛠️ 故障排除

### 常见问题

#### 1. 服务无法启动

```bash
# 查看Pod日志
kubectl logs -f deployment/aetherlife-core -n aetherlife

# 查看事件
kubectl get events -n aetherlife --sort-by='.lastTimestamp'

# 进入Pod调试
kubectl exec -it deployment/aetherlife-core -n aetherlife -- /bin/bash
```

#### 2. Redis连接失败

```bash
# 检查Redis状态
kubectl get svc aetherlife-redis -n aetherlife
kubectl logs deployment/aetherlife-redis -n aetherlife

# 测试连接
kubectl run redis-test --rm -it --image=redis:7-alpine -- redis-cli -h aetherlife-redis ping
```

#### 3. Kafka消息堆积

```bash
# 进入Kafka容器
kubectl exec -it deployment/aetherlife-kafka -n aetherlife -- /bin/bash

# 查看Topic
kafka-topics.sh --bootstrap-server localhost:9092 --list

# 查看消费者组
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# 重置偏移量（谨慎使用！）
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group aetherlife-group \
  --topic tick_data \
  --reset-offsets --to-earliest --execute
```

#### 4. 内存泄漏

```bash
# 查看内存使用
kubectl top pods -n aetherlife

# 重启Pod
kubectl rollout restart deployment/aetherlife-core -n aetherlife

# 启用内存profiling（开发环境）
kubectl exec -it deployment/aetherlife-core -n aetherlife -- \
  python -m memory_profiler src/aetherlife/run.py
```

---

## 📈 性能优化

### 1. 资源配置建议

| 环境 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|------------|-----------|----------------|--------------|
| 开发 | 500m | 1000m | 1Gi | 2Gi |
| 测试 | 1000m | 2000m | 2Gi | 4Gi |
| 生产 | 2000m | 4000m | 4Gi | 8Gi |

### 2. 数据库优化

**Redis:**
```bash
# 配置最大内存和淘汰策略
maxmemory 2gb
maxmemory-policy allkeys-lru

# 启用RDB持久化
save 900 1
save 300 10
save 60 10000
```

**ClickHouse:**
```xml
<!-- configs/clickhouse/config.xml -->
<max_memory_usage>8000000000</max_memory_usage>
<max_bytes_before_external_sort>10000000000</max_bytes_before_external_sort>
```

### 3. Kafka优化

```bash
# 增加分区数（提高并行度）
kafka-topics.sh --bootstrap-server kafka:9092 \
  --alter --topic tick_data --partitions 10

# 配置压缩
compression.type=lz4
```

---

## 🔄 更新和回滚

### 滚动更新

```bash
# 更新镜像
kubectl set image deployment/aetherlife-core \
  aetherlife=aetherlife:v2.0.0 \
  -n aetherlife

# 查看更新进度
kubectl rollout status deployment/aetherlife-core -n aetherlife
```

### 回滚

```bash
# 查看版本历史
kubectl rollout history deployment/aetherlife-core -n aetherlife

# 回滚到上一版本
kubectl rollout undo deployment/aetherlife-core -n aetherlife

# 回滚到指定版本
kubectl rollout undo deployment/aetherlife-core \
  --to-revision=3 \
  -n aetherlife
```

---

## 📞 支持

如有问题，请：

1. 查看[故障排除文档](TROUBLESHOOTING.md)
2. 提交[GitHub Issue](https://github.com/your-org/aetherlife/issues)
3. 加入[Discord社区](https://discord.gg/aetherlife)

---

**最后更新**: 2025年2月21日
