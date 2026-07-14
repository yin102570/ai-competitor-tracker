"""
Audit业务逻辑层 - 审计日志查询、统计、导出
权限: 仅admin可访问
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse, AuditStatsResponse

CST = timezone(timedelta(hours=8))


class AuditService:
    """审计服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 审计日志查询
    # ============================================================

    async def list_logs(
        self,
        current_user: User,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        user_id: int | None = None,
        path: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLogResponse], int]:
        """
        审计日志查询
        权限: 仅admin
        支持按时间范围/用户/路径/方法/状态码筛选
        """
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        filters = []
        if start_time:
            filters.append(AuditLog.created_at >= start_time)
        if end_time:
            filters.append(AuditLog.created_at <= end_time)
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if path:
            filters.append(AuditLog.path.ilike(f"%{path}%"))
        if method:
            filters.append(AuditLog.method == method.upper())
        if status_code is not None:
            filters.append(AuditLog.status_code == status_code)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            query
            .order_by(desc(AuditLog.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = result.scalars().all()

        return [AuditLogResponse.model_validate(l) for l in logs], total

    # ============================================================
    # 审计统计
    # ============================================================

    async def get_stats(
        self,
        current_user: User,
        days: int = 7,
    ) -> AuditStatsResponse:
        """
        审计统计
        权限: 仅admin
        """
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        start_time = datetime.now(CST) - timedelta(days=days)

        # 总请求数
        total_result = await self.db.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.created_at >= start_time
            )
        )
        total_requests = total_result.scalar_one() or 0

        # 总消耗
        cost_result = await self.db.execute(
            select(func.sum(AuditLog.cost_tokens)).where(
                AuditLog.created_at >= start_time
            )
        )
        total_cost = cost_result.scalar_one() or 0

        # 平均响应时间
        avg_time_result = await self.db.execute(
            select(func.avg(AuditLog.response_time_ms)).where(
                AuditLog.created_at >= start_time
            )
        )
        avg_response_time = avg_time_result.scalar_one() or 0.0

        # 错误率
        error_result = await self.db.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.created_at >= start_time,
                AuditLog.status_code >= 400,
            )
        )
        error_count = error_result.scalar_one() or 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0

        # 热门路径
        top_paths_result = await self.db.execute(
            select(AuditLog.path, func.count().label("count"))
            .where(AuditLog.created_at >= start_time)
            .group_by(AuditLog.path)
            .order_by(desc("count"))
            .limit(10)
        )
        top_paths = [{"path": p, "count": c} for p, c in top_paths_result.all()]

        # 活跃用户
        top_users_result = await self.db.execute(
            select(AuditLog.user_id, AuditLog.user_email, func.count().label("count"))
            .where(
                AuditLog.created_at >= start_time,
                AuditLog.user_id.isnot(None),
            )
            .group_by(AuditLog.user_id, AuditLog.user_email)
            .order_by(desc("count"))
            .limit(10)
        )
        top_users = [
            {"user_id": uid, "email": email, "count": c}
            for uid, email, c in top_users_result.all()
        ]

        return AuditStatsResponse(
            total_requests=total_requests,
            total_cost=total_cost,
            avg_response_time_ms=round(avg_response_time, 2),
            error_rate_pct=round(error_rate, 2),
            top_paths=top_paths,
            top_users=top_users,
            time_range=f"{days}d",
        )
