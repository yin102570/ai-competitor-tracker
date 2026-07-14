"""
Sentiment模块API路由 - 舆情面板、趋势分析、情感分析、热点事件
路由前缀: /api/v1/sentiment

接口清单:
  GET    /dashboard              舆情面板聚合数据（突出功能）
  GET    /trends                 热点追踪趋势图数据
  POST   /analyze                情感分析（按量计费 ¥0.5/次）
  GET    /{slug}/events          指定竞品热点事件列表
  GET    /records                舆情记录列表（支持筛选）
"""

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DBSession, PaginationDep
from app.schemas.common import PaginatedResponse
from app.schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentDashboardResponse,
    SentimentEventResponse,
    SentimentRecordListItem,
    SentimentTrendsResponse,
)
from app.services.sentiment_service import SentimentService

router = APIRouter(prefix="/sentiment", tags=["舆情分析"])


# ============================================================
# 舆情面板
# ============================================================

@router.get(
    "/dashboard",
    response_model=SentimentDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="舆情面板",
    description="舆情面板聚合数据 — 总览统计、各竞品舆情概览、热点事件",
)
async def get_dashboard(
    db: DBSession,
) -> SentimentDashboardResponse:
    """舆情面板"""
    service = SentimentService(db)
    return await service.get_dashboard()


# ============================================================
# 趋势分析
# ============================================================

@router.get(
    "/trends",
    response_model=SentimentTrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="热点追踪趋势",
    description="热点追踪趋势图数据，支持按竞品筛选",
)
async def get_trends(
    db: DBSession,
    days: int = Query(default=30, ge=7, le=90, description="时间范围天数"),
    competitor_slug: str | None = Query(default=None, description="竞品slug筛选"),
) -> SentimentTrendsResponse:
    """热点追踪趋势"""
    service = SentimentService(db)
    return await service.get_trends(days=days, competitor_slug=competitor_slug)


# ============================================================
# 情感分析（按量计费）
# ============================================================

@router.post(
    "/analyze",
    response_model=SentimentAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="情感分析",
    description="对输入文本进行情感分析，按量计费¥0.5/次。可选关联竞品保存结果",
)
async def analyze_sentiment(
    request: SentimentAnalyzeRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> SentimentAnalyzeResponse:
    """情感分析"""
    service = SentimentService(db)
    return await service.analyze(request, current_user)


# ============================================================
# 热点事件
# ============================================================

@router.get(
    "/{slug}/events",
    response_model=PaginatedResponse[SentimentEventResponse],
    status_code=status.HTTP_200_OK,
    summary="热点事件",
    description="获取指定竞品的热点事件列表，按情感强度排序",
)
async def get_events(
    slug: str,
    db: DBSession,
    pagination: PaginationDep,
) -> PaginatedResponse[SentimentEventResponse]:
    """热点事件"""
    service = SentimentService(db)
    items, total = await service.get_events(
        slug=slug,
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
# 舆情记录列表
# ============================================================

@router.get(
    "/records",
    response_model=PaginatedResponse[SentimentRecordListItem],
    status_code=status.HTTP_200_OK,
    summary="舆情记录列表",
    description="舆情记录列表，支持按竞品/来源/情感标签筛选",
)
async def list_records(
    db: DBSession,
    pagination: PaginationDep,
    competitor_slug: str | None = Query(default=None, description="竞品筛选"),
    source: str | None = Query(default=None, description="来源筛选"),
    sentiment_label: str | None = Query(
        default=None,
        pattern="^(positive|neutral|negative)$",
        description="情感标签筛选",
    ),
) -> PaginatedResponse[SentimentRecordListItem]:
    """舆情记录列表"""
    service = SentimentService(db)
    records, total = await service.list_records(
        competitor_slug=competitor_slug,
        source=source,
        sentiment_label=sentiment_label,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    items = []
    for r in records:
        topics = None
        if r.topics:
            import json
            try:
                topics = json.loads(r.topics)
            except (json.JSONDecodeError, TypeError):
                topics = None
        items.append(SentimentRecordListItem(
            id=r.id,
            competitor_slug=r.competitor_slug,
            source=r.source,
            sentiment_score=r.sentiment_score,
            sentiment_label=r.sentiment_label,
            topics=topics,
            published_at=r.published_at,
            created_at=r.created_at,
        ))

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )
