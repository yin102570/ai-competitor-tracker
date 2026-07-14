"""
Dashboard模块Schema - 综合看板数据聚合 + WebSocket实时推送
对齐设计文档§4接口契约
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# === 综合看板 ===

class CompetitorOverview(BaseModel):
    """单个竞品概览卡片"""
    slug: str
    name: str
    category: str
    monthly_visits: int | None = None
    ios_downloads: int | None = None
    android_downloads: int | None = None
    arena_score: float | None = None
    arena_rank: int | None = None
    sentiment_score: int = Field(..., description="情感得分 0-100")
    trend: str | None = None
    hot_events: list[str] = Field(default_factory=list)


class SentimentSummary(BaseModel):
    """舆情总览"""
    total_mentions: int
    positive_pct: int
    neutral_pct: int
    negative_pct: int
    trending_topics: list[str] = Field(default_factory=list)
    alert_count: int = Field(default=0, description="预警数量")


class SpiderStatus(BaseModel):
    """爬虫运行状态"""
    total_tasks: int
    running_tasks: int
    success_tasks_24h: int
    failed_tasks_24h: int
    next_scheduled: str | None = None


class DashboardOverviewResponse(BaseModel):
    """综合看板响应 - GET /api/v1/dashboard/overview"""
    competitors: list[CompetitorOverview] = Field(default_factory=list)
    sentiment: SentimentSummary
    spiders: SpiderStatus
    system: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


# === WebSocket 实时推送 ===

class WSMessage(BaseModel):
    """WebSocket消息基类"""
    type: str = Field(..., description="消息类型")
    timestamp: datetime


class WSSentimentUpdate(WSMessage):
    """舆情更新推送"""
    type: str = "sentiment_update"
    competitor_slug: str
    new_mentions: int
    sentiment_shift: str = Field(..., description="positive/negative/neutral")
    sample_content: str | None = None


class WSAlert(WSMessage):
    """预警推送"""
    type: str = "alert"
    alert_type: str = Field(..., description="sentiment_spike/competitor_launch/pricing_change")
    title: str
    description: str
    severity: str = Field(..., description="high/medium/low")


class WSSystemStatus(WSMessage):
    """系统状态推送"""
    type: str = "system_status"
    status: str = Field(..., description="healthy/degraded/down")
    active_connections: int
