"""
Admin模块API路由 - 系统配置、健康检查、备份
路由前缀: /api/v1/admin
权限: config/backup仅admin, health公开

接口清单:
  GET    /config                获取系统配置
  PUT    /config                更新系统配置
  POST   /backup                手动触发数据备份
  GET    /health                系统健康检查（公开）
"""

from fastapi import APIRouter, status

from app.core.deps import AnyUser, DBSession
from app.schemas.admin import (
    BackupResponse,
    HealthCheckResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["系统管理"])


# ============================================================
# 系统配置
# ============================================================

@router.get(
    "/config",
    response_model=SystemConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="获取系统配置",
    description="获取当前系统运行配置（敏感信息已脱敏）。仅admin可访问",
)
async def get_system_config(
    db: DBSession,
    current_user: AnyUser,
) -> SystemConfigResponse:
    """获取系统配置 - admin only"""
    service = AdminService(db)
    return service.get_system_config(current_user)


@router.put(
    "/config",
    response_model=SystemConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="更新系统配置",
    description="更新系统运行配置（内存级，重启恢复）。仅admin可访问",
)
async def update_system_config(
    db: DBSession,
    current_user: AnyUser,
    config_update: SystemConfigUpdate,
) -> SystemConfigResponse:
    """更新系统配置 - admin only"""
    service = AdminService(db)
    return service.update_system_config(current_user, config_update)


# ============================================================
# 数据备份
# ============================================================

@router.post(
    "/backup",
    response_model=BackupResponse,
    status_code=status.HTTP_200_OK,
    summary="手动触发备份",
    description="手动触发数据库备份任务。仅admin可访问。扩展入口：可接入S3/OSS",
)
async def trigger_backup(
    db: DBSession,
    current_user: AnyUser,
) -> BackupResponse:
    """手动触发数据备份 - admin only"""
    service = AdminService(db)
    return await service.trigger_backup(current_user)


# ============================================================
# 健康检查
# ============================================================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="系统健康检查",
    description="系统健康检查端点（公开访问）。检查数据库、Redis、DeepSeek API连通性",
)
async def health_check(db: DBSession) -> HealthCheckResponse:
    """系统健康检查 - 公开访问"""
    service = AdminService(db)
    return await service.health_check()
