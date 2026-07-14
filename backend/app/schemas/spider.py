"""
Spiders模块Schema - 爬虫任务触发、查询、调度配置
对齐设计文档§4接口契约
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, PaginatedResponse


class SpiderTriggerRequest(BaseModel):
    """手动触发爬虫任务 - POST /api/v1/spiders/trigger"""
    competitor_slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="目标竞品slug",
    )
    task_type: str = Field(
        ...,
        pattern="^(web|app|sentiment|pricing|model_rank)$",
        description="任务类型",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="优先级 (1=最高, 10=最低)",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="附加参数（如日期范围、来源等）",
    )


class SpiderTaskResponse(ORMModel):
    """爬虫任务响应"""
    id: str
    competitor_slug: str
    task_type: str
    status: str
    result: dict[str, Any] | None = None
    error_msg: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    created_at: datetime


class SpiderTaskListItem(ORMModel):
    """爬虫任务列表项"""
    id: str
    competitor_slug: str
    task_type: str
    status: str
    error_msg: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class SpiderScheduleResponse(BaseModel):
    """爬虫调度配置响应"""
    schedule: list[dict[str, Any]] = Field(
        default_factory=list,
        description="调度规则列表",
    )
    concurrency_limit: int = Field(..., description="并发上限")
    rate_limit_per_sec: int = Field(..., description="每秒频率限制")
