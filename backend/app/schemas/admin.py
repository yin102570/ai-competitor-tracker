"""
Admin模块Schema - 系统配置、健康检查、备份
对齐设计文档§2.8接口契约
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SystemConfigResponse(BaseModel):
    """系统配置响应"""
    app_name: str
    app_version: str
    environment: str
    database_url_masked: str
    redis_url_masked: str
    deepseek_api_configured: bool
    cors_origins: list[str]
    max_quota_per_day: int
    default_page_size: int
    max_page_size: int
    jwt_access_token_expire_minutes: int
    jwt_refresh_token_expire_days: int


class SystemConfigUpdate(BaseModel):
    """系统配置更新请求"""
    max_quota_per_day: int | None = Field(None, ge=1, le=10000, description="每日最大配额")
    default_page_size: int | None = Field(None, ge=1, le=100, description="默认分页大小")
    max_page_size: int | None = Field(None, ge=1, le=500, description="最大分页大小")
    jwt_access_token_expire_minutes: int | None = Field(None, ge=5, le=10080, description="JWT访问令牌过期时间(分钟)")
    jwt_refresh_token_expire_days: int | None = Field(None, ge=1, le=90, description="JWT刷新令牌过期时间(天)")


class BackupResponse(BaseModel):
    """备份响应"""
    success: bool
    backup_id: str
    backup_path: str | None
    tables_backed_up: list[str]
    timestamp: datetime
    size_bytes: int | None
    message: str


class HealthCheckComponent(BaseModel):
    """健康检查组件状态"""
    name: str
    status: str  # ok / degraded / down
    latency_ms: float | None = None
    detail: dict[str, Any] | None = None


class HealthCheckResponse(BaseModel):
    """系统健康检查响应"""
    status: str  # healthy / degraded / unhealthy
    timestamp: datetime
    uptime_seconds: float
    version: str
    components: list[HealthCheckComponent]
