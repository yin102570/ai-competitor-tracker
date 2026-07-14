"""
Audit模块API路由 - 审计日志查询与统计
路由前缀: /api/v1/audit
权限: 仅admin

接口清单:
  GET    /logs                  审计日志查询（支持多维度筛选）
  GET    /stats                 审计统计（近N天）
"""

from datetime import datetime

from fastapi import APIRouter, Query, status

from app.core.deps import AnyUser, DBSession
from app.schemas.audit import AuditLogResponse, AuditStatsResponse
from app.schemas.common import PaginatedResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["审计日志"])


# ============================================================
# 审计日志查询
# ============================================================

@router.get(
    "/logs",
    response_model=PaginatedResponse[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="审计日志查询",
    description="查询审计日志，支持按时间范围/用户/路径/方法/状态码筛选。仅admin可访问",
)
async def list_audit_logs(
    db: DBSession,
    current_user: AnyUser,
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    user_id: int | None = Query(None, description="用户ID"),
    path: str | None = Query(None, description="请求路径（模糊匹配）"),
    method: str | None = Query(None, description="HTTP方法"),
    status_code: int | None = Query(None, description="HTTP状态码"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> PaginatedResponse[AuditLogResponse]:
    """审计日志查询 - admin only"""
    service = AuditService(db)
    items, total = await service.list_logs(
        current_user=current_user,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
        path=path,
        method=method,
        status_code=status_code,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ============================================================
# 审计统计
# ============================================================

@router.get(
    "/stats",
    response_model=AuditStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="审计统计",
    description="返回近N天的审计统计数据。仅admin可访问",
)
async def get_audit_stats(
    db: DBSession,
    current_user: AnyUser,
    days: int = Query(7, ge=1, le=90, description="统计天数"),
) -> AuditStatsResponse:
    """审计统计 - admin only"""
    service = AuditService(db)
    return await service.get_stats(current_user, days=days)
