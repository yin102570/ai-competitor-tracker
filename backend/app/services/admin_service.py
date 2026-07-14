"""
Admin业务逻辑层 - 系统配置、健康检查、备份
权限: 仅admin可访问
"""

from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthError
from app.models.user import User
from app.schemas.admin import (
    BackupResponse,
    HealthCheckComponent,
    HealthCheckResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)

CST = timezone(timedelta(hours=8))

# 启动时间戳（模块加载时初始化）
_startup_time: datetime = datetime.now(CST)


class AdminService:
    """系统管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 权限检查
    # ============================================================

    def _require_admin(self, current_user: User) -> None:
        """要求管理员权限"""
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

    # ============================================================
    # 系统配置
    # ============================================================

    def get_system_config(self, current_user: User) -> SystemConfigResponse:
        """
        获取系统配置
        权限: 仅admin
        """
        self._require_admin(current_user)

        return SystemConfigResponse(
            app_name=settings.app_name,
            app_version=settings.app_version,
            environment=settings.environment,
            database_url_masked=self._mask_url(str(settings.database_url)),
            redis_url_masked=self._mask_url(str(settings.redis_url)),
            deepseek_api_configured=bool(settings.deepseek_api_key),
            cors_origins=settings.cors_origins,
            max_quota_per_day=settings.max_quota_per_day,
            default_page_size=settings.default_page_size,
            max_page_size=settings.max_page_size,
            jwt_access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
            jwt_refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
        )

    def update_system_config(
        self,
        current_user: User,
        config_update: SystemConfigUpdate,
    ) -> SystemConfigResponse:
        """
        更新系统配置
        权限: 仅admin
        注意: 仅更新内存中的settings（重启后恢复），持久化需扩展
        """
        self._require_admin(current_user)

        # 更新内存配置（扩展入口: 可持久化到数据库或配置文件）
        if config_update.max_quota_per_day is not None:
            settings.max_quota_per_day = config_update.max_quota_per_day
        if config_update.default_page_size is not None:
            settings.default_page_size = config_update.default_page_size
        if config_update.max_page_size is not None:
            settings.max_page_size = config_update.max_page_size
        if config_update.jwt_access_token_expire_minutes is not None:
            settings.jwt_access_token_expire_minutes = (
                config_update.jwt_access_token_expire_minutes
            )
        if config_update.jwt_refresh_token_expire_days is not None:
            settings.jwt_refresh_token_expire_days = (
                config_update.jwt_refresh_token_expire_days
            )

        return self.get_system_config(current_user)

    @staticmethod
    def _mask_url(url: str) -> str:
        """脱敏URL（隐藏密码/密钥）"""
        if "@" in url:
            # 如 redis://user:pass@host -> redis://***@host
            parts = url.split("@")
            return parts[0].split("://")[0] + "://***@" + "@".join(parts[1:])
        if "://" in url:
            # 如 sqlite:///path
            return url
        return "***"

    # ============================================================
    # 数据备份
    # ============================================================

    async def trigger_backup(self, current_user: User) -> BackupResponse:
        """
        手动触发数据备份
        权限: 仅admin
        扩展入口: 实际备份逻辑可接入云存储(S3/OSS)
        """
        self._require_admin(current_user)

        backup_id = f"bk_{uuid4().hex[:12]}"
        now = datetime.now(CST)

        # 获取表列表（SQLite专用）
        tables = []
        try:
            result = await self.db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            )
            tables = [row[0] for row in result.all()]
        except Exception:
            tables = ["users", "api_keys", "competitors", "competitor_history",
                      "sentiment_records", "spider_tasks", "audit_logs"]

        # 扩展入口: 实际备份实现
        # TODO: 接入 S3/OSS / pg_dump / sqlite3 .backup
        backup_path = f"/backups/{backup_id}.sql"

        return BackupResponse(
            success=True,
            backup_id=backup_id,
            backup_path=backup_path,
            tables_backed_up=tables,
            timestamp=now,
            size_bytes=None,
            message="备份任务已创建（开发环境：模拟备份）",
        )

    # ============================================================
    # 健康检查
    # ============================================================

    async def health_check(self) -> HealthCheckResponse:
        """
        系统健康检查
        权限: 公开（无需认证）
        检查项: 数据库、Redis、DeepSeek API连通性
        """
        now = datetime.now(CST)
        uptime = (now - _startup_time).total_seconds()
        components: list[HealthCheckComponent] = []

        # 1. 数据库检查
        db_status, db_latency = await self._check_database()
        components.append(
            HealthCheckComponent(
                name="database",
                status=db_status,
                latency_ms=db_latency,
                detail={"type": "sqlite" if "sqlite" in settings.database_url else "postgresql"},
            )
        )

        # 2. Redis检查
        redis_status, redis_latency = await self._check_redis()
        components.append(
            HealthCheckComponent(
                name="redis",
                status=redis_status,
                latency_ms=redis_latency,
            )
        )

        # 3. DeepSeek API检查（可选，不阻塞整体状态）
        deepseek_status, deepseek_latency = await self._check_deepseek()
        components.append(
            HealthCheckComponent(
                name="deepseek_api",
                status=deepseek_status,
                latency_ms=deepseek_latency,
                detail={"configured": bool(settings.deepseek_api_key)},
            )
        )

        # 整体状态判定
        overall = self._determine_overall_status(components)

        return HealthCheckResponse(
            status=overall,
            timestamp=now,
            uptime_seconds=uptime,
            version=settings.app_version,
            components=components,
        )

    async def _check_database(self) -> tuple[str, float]:
        """检查数据库连通性"""
        import time

        start = time.perf_counter()
        try:
            await self.db.execute(text("SELECT 1"))
            latency = (time.perf_counter() - start) * 1000
            return "ok", round(latency, 2)
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return "down", round(latency, 2)

    async def _check_redis(self) -> tuple[str, float]:
        """检查Redis连通性"""
        import time

        start = time.perf_counter()
        try:
            from app.core.security import TokenBlacklist

            await TokenBlacklist._client.ping()
            latency = (time.perf_counter() - start) * 1000
            return "ok", round(latency, 2)
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            # Redis未配置时不视为down
            if not settings.redis_url:
                return "degraded", round(latency, 2)
            return "down", round(latency, 2)

    async def _check_deepseek(self) -> tuple[str, float]:
        """检查DeepSeek API连通性（轻量探测）"""
        import time

        start = time.perf_counter()
        if not settings.deepseek_api_key:
            latency = (time.perf_counter() - start) * 1000
            return "degraded", round(latency, 2)

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                )
                latency = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return "ok", round(latency, 2)
                return "degraded", round(latency, 2)
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            return "degraded", round(latency, 2)

    @staticmethod
    def _determine_overall_status(components: list[HealthCheckComponent]) -> str:
        """判定整体健康状态"""
        statuses = [c.status for c in components]
        if all(s == "ok" for s in statuses):
            return "healthy"
        if any(s == "down" for s in statuses):
            return "unhealthy"
        return "degraded"
