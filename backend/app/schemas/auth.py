"""
认证模块Schema - 请求/响应数据验证
对齐阶段四设计文档 §4 接口契约
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


# === 请求Schema ===

class LoginRequest(BaseModel):
    """登录请求 - POST /api/v1/auth/login"""
    email: str = Field(..., description="用户邮箱")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="用户密码（8-128位）",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """简单邮箱格式校验"""
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("邮箱格式不正确")
        return v


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求 - POST /api/v1/auth/refresh"""
    refresh_token: str = Field(..., description="刷新令牌")


class APIKeyCreateRequest(BaseModel):
    """创建API Key请求 - POST /api/v1/auth/api-keys"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="API Key名称",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="过期天数（1-365），不传表示永不过期",
    )


# === 响应Schema ===

class TokenResponse(BaseModel):
    """登录/刷新成功响应"""
    access_token: str = Field(..., description="访问令牌（30分钟有效）")
    refresh_token: str = Field(..., description="刷新令牌（7天有效）")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌有效期（秒）")


class UserResponse(ORMModel):
    """用户信息响应"""
    id: int
    email: str
    name: str
    role: str
    daily_quota: int
    quota_used: int
    quota_remaining: int
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class APIKeyResponse(ORMModel):
    """API Key信息响应（不含明文密钥）"""
    id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class APIKeyCreatedResponse(BaseModel):
    """API Key创建响应（含明文密钥，仅此一次）"""
    id: int
    name: str
    api_key: str = Field(..., description="API Key明文（仅创建时返回，请妥善保管）")
    key_prefix: str
    expires_at: datetime | None = None
    created_at: datetime
    warning: str = Field(
        default="此API Key明文仅显示一次，请立即保存。后续无法再次查看。",
        description="安全提示",
    )


class LogoutResponse(BaseModel):
    """登出响应"""
    success: bool = True
    message: str = "已成功登出，令牌已吊销"
