"""
Sentiment模块Schema - 舆情面板、趋势分析、情感分析、热点事件
对齐设计文档§4接口契约
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# === 舆情面板 ===

class SentimentDistribution(BaseModel):
    """情感分布"""
    positive: int = Field(..., description="正面占比%")
    neutral: int = Field(..., description="中性占比%")
    negative: int = Field(..., description="负面占比%")


class HotEvent(BaseModel):
    """热点事件"""
    title: str = Field(..., description="事件标题")
    impact: str = Field(..., description="影响级别: high/medium/low")


class CompetitorSentiment(BaseModel):
    """单个竞品舆情概览"""
    slug: str
    sentiment_score: int = Field(..., description="综合情感得分 0-100")
    mention_count: int = Field(..., description="提及次数")
    hot_events: list[HotEvent] = Field(default_factory=list)


class SentimentDashboardResponse(BaseModel):
    """舆情面板聚合响应 - GET /api/v1/sentiment/dashboard"""
    overview: dict[str, Any] = Field(..., description="总览数据")
    competitors: list[CompetitorSentiment] = Field(default_factory=list)
    updated_at: datetime


# === 趋势分析 ===

class TrendPoint(BaseModel):
    """趋势点"""
    date: date
    positive: int
    neutral: int
    negative: int
    total: int


class SentimentTrendsResponse(BaseModel):
    """热点追踪趋势响应 - GET /api/v1/sentiment/trends"""
    time_range: str
    data: list[TrendPoint] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


# === 情感分析 ===

class SentimentAnalyzeRequest(BaseModel):
    """情感分析请求 - POST /api/v1/sentiment/analyze"""
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="待分析的文本内容（最大5000字）",
    )
    competitor_slug: str | None = Field(
        default=None,
        description="关联的竞品slug（可选）",
    )


class SentimentAnalyzeResponse(BaseModel):
    """情感分析响应"""
    sentiment_score: float = Field(..., description="情感得分 -1.0 ~ +1.0")
    sentiment_label: str = Field(..., description="positive/neutral/negative")
    confidence: float = Field(..., description="置信度 0.0 ~ 1.0")
    topics: list[str] = Field(default_factory=list, description="提取的话题")
    cost: float = Field(..., description="本次分析扣费")


# === 热点事件 ===

class SentimentEventResponse(BaseModel):
    """热点事件列表项"""
    id: int
    competitor_slug: str
    source: str
    content: str
    sentiment_score: float
    sentiment_label: str
    topics: list[str] | None = None
    published_at: datetime
    created_at: datetime


# === 舆情记录列表 ===

class SentimentRecordListItem(ORMModel):
    """舆情记录列表项"""
    id: int
    competitor_slug: str
    source: str
    sentiment_score: float
    sentiment_label: str
    topics: list[str] | None = None
    published_at: datetime
    created_at: datetime
