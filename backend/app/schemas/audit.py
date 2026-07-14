"""
Audit模块Schema - 审计日志查询、统计
对齐设计文档§4接口契约
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AuditLogResponse(ORMModel):
    """审计日志响应项"""
    id: int
    request_id: str
    user_id: int | None
    user_email: str | None
    method: str
    path: str
    status_code: int
    client_ip: str | None
    cost_tokens: int
    response_time_ms: int
    error_code: str | None
    created_at: datetime


class AuditStatsResponse(BaseModel):
    """审计统计响应"""
    total_requests: int
    total_cost: int
    avg_response_time_ms: float
    error_rate_pct: float
    top_paths: list[dict[str, int]] = Field(default_factory=list)
    top_users: list[dict[str, int]] = Field(default_factory=list)
    time_range: str
