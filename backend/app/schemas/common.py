"""
通用Schema - 分页、统一响应、通用字段
所有模块共享
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """支持从ORM对象创建的基类Schema"""
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    """分页查询参数"""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class SuccessResponse(BaseModel):
    """统一成功响应"""
    success: bool = True
    message: str = "操作成功"
    data: Any | None = None


class ErrorResponse(BaseModel):
    """统一错误响应 - 对齐设计文档§6"""
    error_code: str
    message: str
    detail: dict[str, Any] = {}
    request_id: str
    timestamp: datetime


class TokenPayload(BaseModel):
    """JWT Token 载荷"""
    sub: str  # user_id
    role: str
    exp: datetime
    jti: str  # JWT ID，用于黑名单
    type: str  # "access" | "refresh"
