"""
Competitors业务逻辑层 - 竞品CRUD、对标分析、历史趋势、定价信息
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthError,
    BusinessError,
    NotFoundError,
)
from app.models.competitor import Competitor, CompetitorHistory
from app.models.user import User
from app.schemas.competitor import (
    CompetitorCompareRequest,
    CompetitorCompareResponse,
    CompetitorCreateRequest,
    CompetitorDetailResponse,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorUpdateRequest,
    HistoryResponse,
    PricingResponse,
)
from app.services.auth_service import AuthService

CST = timezone(timedelta(hours=8))

# 对标分析单价（¥/次）
COMPARE_COST_PER_REPORT = 5.0


class CompetitorService:
    """竞品服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthService(db)

    # ============================================================
    # 竞品列表
    # ============================================================

    async def list_competitors(
        self,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CompetitorListResponse], int]:
        """
        竞品列表（含最新快照）
        支持按分类筛选
        """
        query = select(Competitor)
        count_query = select(func.count()).select_from(Competitor)

        if category:
            query = query.where(Competitor.category == category)
            count_query = count_query.where(Competitor.category == category)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            query
            .order_by(Competitor.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        competitors = result.scalars().all()

        # 为每个竞品附加最新快照
        items = []
        for comp in competitors:
            latest = await self._get_latest_snapshot(comp.slug)
            items.append(CompetitorListResponse(
                slug=comp.slug,
                name=comp.name,
                company=comp.company,
                category=comp.category,
                monthly_visits=latest.monthly_visits if latest else None,
                trend=await self._calc_trend(comp.slug),
                ios_downloads=latest.ios_downloads if latest else None,
                android_downloads=latest.android_downloads if latest else None,
                arena_score=latest.arena_score if latest else None,
                arena_rank=latest.arena_rank if latest else None,
                updated_at=comp.updated_at,
                created_at=comp.created_at,
            ))

        return items, total

    # ============================================================
    # 竞品详情
    # ============================================================

    async def get_competitor(self, slug: str) -> CompetitorDetailResponse:
        """获取竞品详情（含最新历史快照）"""
        comp = await self._get_by_slug(slug)
        latest = await self._get_latest_snapshot(slug)

        return CompetitorDetailResponse(
            slug=comp.slug,
            name=comp.name,
            company=comp.company,
            category=comp.category,
            logo_url=comp.logo_url,
            website=comp.website,
            pricing_info=comp.pricing_info,
            latest_snapshot=HistoryResponse.model_validate(latest) if latest else None,
            created_at=comp.created_at,
            updated_at=comp.updated_at,
        )

    # ============================================================
    # 创建竞品
    # ============================================================

    async def create_competitor(
        self,
        request: CompetitorCreateRequest,
        current_user: User,
    ) -> CompetitorResponse:
        """
        创建竞品
        权限: admin/analyst
        """
        if not current_user.is_analyst_or_above:
            raise AuthError.permission_denied("analyst")

        existing = await self._get_by_slug_or_none(request.slug)
        if existing is not None:
            raise BusinessError.duplicate("slug", request.slug)

        comp = Competitor(
            slug=request.slug,
            name=request.name,
            company=request.company,
            category=request.category,
            logo_url=request.logo_url,
            website=request.website,
            pricing_info=request.pricing_info,
        )
        self.db.add(comp)
        await self.db.flush()

        return CompetitorResponse.model_validate(comp)

    # ============================================================
    # 更新竞品
    # ============================================================

    async def update_competitor(
        self,
        slug: str,
        request: CompetitorUpdateRequest,
        current_user: User,
    ) -> CompetitorResponse:
        """
        更新竞品信息
        权限: admin/analyst
        """
        if not current_user.is_analyst_or_above:
            raise AuthError.permission_denied("analyst")

        comp = await self._get_by_slug(slug)

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(comp, field, value)

        await self.db.flush()
        return CompetitorResponse.model_validate(comp)

    # ============================================================
    # 删除竞品
    # ============================================================

    async def delete_competitor(
        self,
        slug: str,
        current_user: User,
    ) -> None:
        """
        删除竞品（级联删除历史数据）
        权限: admin only
        """
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        comp = await self._get_by_slug(slug)
        await self.db.delete(comp)
        await self.db.flush()

    # ============================================================
    # 历史数据查询
    # ============================================================

    async def get_history(
        self,
        slug: str,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 30,
    ) -> tuple[list[HistoryResponse], int]:
        """查询竞品历史数据"""
        await self._get_by_slug(slug)  # 验证竞品存在

        query = select(CompetitorHistory).where(
            CompetitorHistory.competitor_slug == slug
        )
        count_query = select(func.count()).select_from(CompetitorHistory).where(
            CompetitorHistory.competitor_slug == slug
        )

        if start_date:
            query = query.where(CompetitorHistory.date >= start_date)
            count_query = count_query.where(CompetitorHistory.date >= start_date)
        if end_date:
            query = query.where(CompetitorHistory.date <= end_date)
            count_query = count_query.where(CompetitorHistory.date <= end_date)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one() or 0

        result = await self.db.execute(
            query
            .order_by(CompetitorHistory.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = result.scalars().all()

        return [HistoryResponse.model_validate(r) for r in records], total

    # ============================================================
    # 竞品对标（按量计费）
    # ============================================================

    async def compare(
        self,
        request: CompetitorCompareRequest,
        current_user: User,
    ) -> CompetitorCompareResponse:
        """
        竞品对标分析
        按量计费: ¥5/份对标报告
        """
        # 1. 验证所有slug存在
        competitors_data = []
        for slug in request.slugs:
            comp = await self._get_by_slug(slug)
            latest = await self._get_latest_snapshot(slug)
            competitors_data.append({
                "slug": comp.slug,
                "name": comp.name,
                "company": comp.company,
                "category": comp.category,
                "latest": {
                    "monthly_visits": latest.monthly_visits if latest else None,
                    "ios_downloads": latest.ios_downloads if latest else None,
                    "android_downloads": latest.android_downloads if latest else None,
                    "arena_score": latest.arena_score if latest else None,
                    "arena_rank": latest.arena_rank if latest else None,
                } if latest else None,
            })

        # 2. 消耗配额（对标分析 = 5次查询）
        await self.auth_service.check_and_consume_quota(current_user.id, cost=5)

        # 3. 构建报告
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"

        return CompetitorCompareResponse(
            report_id=report_id,
            cost=COMPARE_COST_PER_REPORT,
            competitors=competitors_data,
        )

    # ============================================================
    # 定价信息
    # ============================================================

    async def get_pricing(self, slug: str) -> PricingResponse:
        """查询竞品定价信息"""
        comp = await self._get_by_slug(slug)
        return PricingResponse(
            slug=comp.slug,
            name=comp.name,
            pricing_info=comp.pricing_info,
        )

    # ============================================================
    # 内部方法
    # ============================================================

    async def _get_by_slug(self, slug: str) -> Competitor:
        """根据slug获取竞品，不存在则抛异常"""
        result = await self.db.execute(
            select(Competitor).where(Competitor.slug == slug)
        )
        comp = result.scalar_one_or_none()
        if comp is None:
            raise NotFoundError.competitor(slug)
        return comp

    async def _get_by_slug_or_none(self, slug: str) -> Competitor | None:
        """根据slug获取竞品，不存在返回None"""
        result = await self.db.execute(
            select(Competitor).where(Competitor.slug == slug)
        )
        return result.scalar_one_or_none()

    async def _get_latest_snapshot(self, slug: str) -> CompetitorHistory | None:
        """获取竞品最新一条快照"""
        result = await self.db.execute(
            select(CompetitorHistory)
            .where(CompetitorHistory.competitor_slug == slug)
            .order_by(CompetitorHistory.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _calc_trend(self, slug: str) -> str | None:
        """
        计算最近30天流量趋势
        返回: "up" / "down" / "stable" / None
        """
        result = await self.db.execute(
            select(CompetitorHistory)
            .where(CompetitorHistory.competitor_slug == slug)
            .order_by(CompetitorHistory.date.desc())
            .limit(2)
        )
        snapshots = result.scalars().all()

        if len(snapshots) < 2:
            return None

        current = snapshots[0].monthly_visits or 0
        previous = snapshots[1].monthly_visits or 0

        if previous == 0:
            return "up" if current > 0 else None

        change = (current - previous) / previous * 100
        if change > 5:
            return "up"
        elif change < -5:
            return "down"
        return "stable"
