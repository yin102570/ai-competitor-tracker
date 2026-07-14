#!/bin/bash
# ============================================================
# 生产环境启动脚本
# 用法: bash scripts/start.sh [dev|prod]
# ============================================================

set -euo pipefail

ENV="${1:-prod}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "============================================"
echo " AI竞品追踪系统 - 启动"
echo " 环境: $ENV"
echo " 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# === 环境检查 ===
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "[ERROR] 缺少依赖: $1"
        exit 1
    fi
}

check_command docker
check_command docker-compose || check_command "docker compose"

# === 加载环境变量 ===
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "[ERROR] 缺少 .env 文件，请从 .env.example 复制并配置"
    exit 1
fi

# === 创建必要目录 ===
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/backups"

# === 启动 ===
cd "$PROJECT_ROOT/docker"

if [ "$ENV" = "dev" ]; then
    echo "[INFO] 启动开发环境..."
    docker compose --env-file ../.env up -d backend redis
    echo "[INFO] 开发环境已启动"
    echo "  API:      http://localhost:8000"
    echo "  Docs:     http://localhost:8000/docs"
    echo "  健康检查: http://localhost:8000/health"
elif [ "$ENV" = "prod" ]; then
    echo "[INFO] 启动生产环境..."
    docker compose --env-file ../.env up -d
    echo "[INFO] 生产环境已启动"
    echo "  API:      http://localhost:80"
    echo "  健康检查: http://localhost/health"
    echo ""
    echo "[INFO] 查看日志: docker compose logs -f backend"
    echo "[INFO] 查看状态: docker compose ps"
else
    echo "[ERROR] 未知环境: $ENV (可选: dev / prod)"
    exit 1
fi

echo "============================================"
echo " 启动完成"
echo "============================================"
