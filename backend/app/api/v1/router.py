"""
API v1 路由聚合器
统一注册所有模块路由，前缀 /api/v1
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    competitors,
    sentiment,
    spiders,
    dashboard,
    audit,
    admin,
    payment,
)

api_router = APIRouter(prefix="/api/v1")

# 注册模块路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(competitors.router)
api_router.include_router(sentiment.router)
api_router.include_router(spiders.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
api_router.include_router(admin.router)
api_router.include_router(payment.router)

# === 未来模块扩展入口 ===
# 示例: from app.api.v1.endpoints import alerts
# api_router.include_router(alerts.router)
