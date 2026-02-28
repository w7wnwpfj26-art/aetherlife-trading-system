# AetherLife Trading System - Dockerfile
# 多阶段构建，生产级配置

# ==================== Stage 1: Base ====================
FROM python:3.11-slim as base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ==================== Stage 2: Dependencies ====================
FROM base as dependencies

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ==================== Stage 3: Production ====================
FROM base as production

# 复制Python依赖
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# 创建非root用户
RUN useradd -m -u 1000 aether && \
    mkdir -p /app /data /logs && \
    chown -R aether:aether /app /data /logs

# 切换到非root用户
USER aether

# 复制应用代码
COPY --chown=aether:aether . /app

WORKDIR /app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令（由docker-compose覆盖）
CMD ["python", "-m", "aetherlife.run"]

# ==================== Stage 4: Development ====================
FROM dependencies as development

# 安装开发工具
RUN pip install \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    flake8 \
    mypy \
    ipython \
    jupyter

# 复制应用代码
COPY . /app

WORKDIR /app

# 开发模式不需要健康检查
CMD ["python", "-m", "aetherlife.run"]
