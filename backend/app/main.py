"""
FastAPI 应用入口
职责: 应用生命周期管理、中间件注册、路由挂载、异常处理
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
)
from app.core.security import TokenBlacklist
from app.api.v1.router import api_router
from app.db.session import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期: 启动时初始化，关闭时清理"""
    # === 启动 ===
    # 开发环境自动建表
    if settings.is_development:
        await init_db()

    # 安全自检
    warnings = settings.validate_security()
    for w in warnings:
        import logging
        logging.getLogger("app").warning(f"[安全警告] {w}")

    yield

    # === 关闭 ===
    await close_db()
    await TokenBlacklist.close()


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="AI对话产品竞品动态追踪与智能对标分析系统",
        description="基于大模型的AI对话产品竞品动态追踪与智能对标分析系统API",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # === 中间件 ===
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """为每个请求注入唯一 request_id，贯穿日志和错误响应"""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # === 异常处理 ===
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # === 路由 ===
    app.include_router(api_router)

    # === 健康检查 ===
    @app.get("/health", tags=["系统"])
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "1.0.0",
            "env": settings.app_env,
        }

    return app


# 全局应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
    )
