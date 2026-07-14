"""
Competitors模块API路由 - 竞品CRUD、对标分析、历史趋势、定价信息
路由前缀: /api/v1/competitors

接口清单:
  GET    /                          竞品列表（分页+分类筛选）
  GET    /{slug}                    竞品详情
  POST   /                          创建竞品 (analyst+)
  PUT    /{slug}                    更新竞品 (analyst+)
  DELETE /{slug}                    删除竞品 (admin only)
  GET    /{slug}/history            历史数据（分页+日期范围）
  POST   /compare                   竞品对标分析（按量计费 ¥5/份）
  GET    /{slug}/pricing            定价信息
"""

from datetime import date

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DBSession, PaginationDep
from app.schemas.common import PaginatedResponse, SuccessResponse
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
from app.services.competitor_service import CompetitorService

router = APIRouter(prefix="/competitors", tags=["竞品管理"])


# ============================================================
# 竞品列表
# ============================================================

@router.get(
    "/",
    response_model=PaginatedResponse[CompetitorListResponse],
    status_code=status.HTTP_200_OK,
    summary="竞品列表",
    description="获取竞品列表，支持按分类筛选，包含最新快照数据",
)
async def list_competitors(
    db: DBSession,
    pagination: PaginationDep,
    category: str | None = Query(default=None, description="分类筛选: chatbot/multimodal/search/coding"),
) -> PaginatedResponse[CompetitorListResponse]:
    """竞品列表"""
    service = CompetitorService(db)
    items, total = await service.list_competitors(
        category=category,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


# ============================================================
# 竞品详情
# ============================================================

@router.get(
    "/{slug}",
    response_model=CompetitorDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="竞品详情",
    description="获取竞品完整信息，包含最新历史快照",
)
async def get_competitor(
    slug: str,
    db: DBSession,
) -> CompetitorDetailResponse:
    """竞品详情"""
    service = CompetitorService(db)
    return await service.get_competitor(slug)


# ============================================================
# 创建竞品
# ============================================================

@router.post(
    "/",
    response_model=CompetitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建竞品",
    description="添加新的竞品到追踪列表。需要analyst或admin权限",
)
async def create_competitor(
    request: CompetitorCreateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> CompetitorResponse:
    """创建竞品"""
    service = CompetitorService(db)
    return await service.create_competitor(request, current_user)


# ============================================================
# 更新竞品
# ============================================================

@router.put(
    "/{slug}",
    response_model=CompetitorResponse,
    status_code=status.HTTP_200_OK,
    summary="更新竞品",
    description="更新竞品信息。需要analyst或admin权限",
)
async def update_competitor(
    slug: str,
    request: CompetitorUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> CompetitorResponse:
    """更新竞品"""
    service = CompetitorService(db)
    return await service.update_competitor(slug, request, current_user)


# ============================================================
# 删除竞品
# ============================================================

@router.delete(
    "/{slug}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="删除竞品",
    description="删除竞品及所有关联历史数据。仅admin可操作",
)
async def delete_competitor(
    slug: str,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse:
    """删除竞品"""
    service = CompetitorService(db)
    await service.delete_competitor(slug, current_user)
    return SuccessResponse(message=f"竞品 {slug} 已删除")


# ============================================================
# 历史数据
# ============================================================

@router.get(
    "/{slug}/history",
    response_model=PaginatedResponse[HistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="历史数据",
    description="查询竞品历史快照数据，支持日期范围筛选",
)
async def get_history(
    slug: str,
    db: DBSession,
    pagination: PaginationDep,
    start_date: date | None = Query(default=None, description="起始日期"),
    end_date: date | None = Query(default=None, description="截止日期"),
) -> PaginatedResponse[HistoryResponse]:
    """历史数据"""
    service = CompetitorService(db)
    items, total = await service.get_history(
        slug=slug,
        start_date=start_date,
        end_date=end_date,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


# ============================================================
# 竞品对标（按量计费）
# ============================================================

@router.post(
    "/compare",
    response_model=CompetitorCompareResponse,
    status_code=status.HTTP_200_OK,
    summary="竞品对标分析",
    description="对比多个竞品的关键指标，按量计费¥5/份",
)
async def compare_competitors(
    request: CompetitorCompareRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> CompetitorCompareResponse:
    """竞品对标分析"""
    service = CompetitorService(db)
    return await service.compare(request, current_user)


# ============================================================
# 定价信息
# ============================================================

@router.get(
    "/{slug}/pricing",
    response_model=PricingResponse,
    status_code=status.HTTP_200_OK,
    summary="定价信息",
    description="查询竞品的定价信息",
)
async def get_pricing(
    slug: str,
    db: DBSession,
) -> PricingResponse:
    """定价信息"""
    service = CompetitorService(db)
    return await service.get_pricing(slug)
