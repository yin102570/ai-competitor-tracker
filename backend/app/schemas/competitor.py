"""
Competitors模块Schema - 竞品列表、详情、对标、历史、定价
对齐设计文档§4接口契约
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, PaginatedResponse


# === 响应Schema ===

class CompetitorResponse(ORMModel):
    """竞品列表/详情响应"""
    slug: str
    name: str
    company: str
    category: str
    logo_url: str | None = None
    website: str | None = None
    pricing_info: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorListResponse(ORMModel):
    """竞品列表项（含最新快照数据）"""
    slug: str
    name: str
    company: str
    category: str
    monthly_visits: int | None = None
    trend: str | None = None
    ios_downloads: int | None = None
    android_downloads: int | None = None
    arena_score: float | None = None
    arena_rank: int | None = None
    updated_at: datetime
    created_at: datetime


class CompetitorDetailResponse(ORMModel):
    """竞品详情响应（含最新历史快照）"""
    slug: str
    name: str
    company: str
    category: str
    logo_url: str | None = None
    website: str | None = None
    pricing_info: dict[str, Any] | None = None
    latest_snapshot: "HistoryResponse | None" = None
    created_at: datetime
    updated_at: datetime


class HistoryResponse(ORMModel):
    """历史快照数据"""
    id: int
    competitor_slug: str
    date: date
    monthly_visits: int | None = None
    ios_downloads: int | None = None
    android_downloads: int | None = None
    arena_score: float | None = None
    arena_rank: int | None = None
    created_at: datetime


class CompetitorCompareRequest(BaseModel):
    """竞品对标请求 - POST /api/v1/competitors/compare"""
    slugs: list[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="竞品slug列表（2-10个）",
    )
    metrics: list[str] = Field(
        default=["web_traffic", "app_downloads", "model_rank"],
        description="对标维度: web_traffic/app_downloads/model_rank/sentiment",
    )
    time_range: str = Field(
        default="30d",
        pattern="^(7d|14d|30d|90d)$",
        description="时间范围",
    )


class CompetitorCompareResponse(BaseModel):
    """竞品对标响应（按量计费 ¥5/份）"""
    report_id: str = Field(..., description="报告ID")
    cost: float = Field(..., description="本次查询扣费金额")
    competitors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="竞品对标数据",
    )


class CompetitorCreateRequest(BaseModel):
    """创建竞品请求 (admin/analyst)"""
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-z0-9-]+$",
        description="URL友好标识",
    )
    name: str = Field(..., min_length=1, max_length=200, description="产品名称")
    company: str = Field(..., min_length=1, max_length=200, description="所属公司")
    category: str = Field(..., min_length=1, max_length=50, description="分类")
    logo_url: str | None = Field(default=None, max_length=500, description="Logo URL")
    website: str | None = Field(default=None, max_length=500, description="官网地址")
    pricing_info: dict[str, Any] | None = Field(default=None, description="定价信息")


class CompetitorUpdateRequest(BaseModel):
    """更新竞品请求 (admin/analyst)"""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    logo_url: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)
    pricing_info: dict[str, Any] | None = Field(default=None)


class PricingResponse(BaseModel):
    """定价信息响应"""
    slug: str
    name: str
    pricing_info: dict[str, Any] | None = None


# 解决前向引用
CompetitorDetailResponse.model_rebuild()
