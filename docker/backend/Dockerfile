# ============================================================
# AI竞品追踪系统 - Dockerfile
# 多阶段构建: builder → runtime
# ============================================================

# === 阶段1: 依赖安装 ===
FROM python:3.13-slim AS builder

WORKDIR /build

# 系统依赖（编译用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

# 安装Python依赖到独立目录
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === 阶段2: 运行时镜像 ===
FROM python:3.13-slim AS runtime

# 镜像元数据
LABEL maintainer="ai-competitor-tracker"
LABEL description="AI对话产品竞品动态追踪与智能对标分析系统"
LABEL version="1.0.0"

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# 从builder复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY backend/ .

# 创建必要目录
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_ENV=production \
    APP_DEBUG=false \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200"

# 入口
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--access-log"]
