"""
Users模块Schema - 用户注册、更新、配额查询
对齐阶段四设计文档 §4 接口契约
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class UserRegisterRequest(BaseModel):
    """用户注册请求 - POST /api/v1/users/register"""
    email: str = Field(..., description="用户邮箱")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="用户密码（8-128位，需包含大小写字母和数字）",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="用户显示名称",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """简单邮箱格式校验"""
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """密码强度校验：至少1个大写、1个小写、1个数字"""
        if not any(c.isupper() for c in v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not any(c.islower() for c in v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        return v


class UserUpdateRequest(BaseModel):
    """更新当前用户信息 - PUT /api/v1/users/me"""
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="用户显示名称",
    )


class UserRoleUpdateRequest(BaseModel):
    """修改用户角色 - PUT /api/v1/users/{user_id}/role (admin only)"""
    role: str = Field(
        ...,
        pattern="^(admin|analyst|viewer)$",
        description="目标角色: admin/analyst/viewer",
    )


class UserQuotaResponse(BaseModel):
    """用户配额信息响应"""
    user_id: int = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    daily_quota: int = Field(..., description="每日配额上限")
    quota_used: int = Field(..., description="当日已用配额")
    quota_remaining: int = Field(..., description="剩余配额")
    quota_reset_at: datetime = Field(..., description="配额重置时间")
    is_active: bool = Field(..., description="账户是否激活")


class UserRegisteredResponse(BaseModel):
    """用户注册成功响应"""
    id: int = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    name: str = Field(..., description="用户名称（脱敏处理）")
    role: str = Field(..., description="默认角色")
    daily_quota: int = Field(..., description="每日免费配额")
    created_at: datetime = Field(..., description="注册时间")

    @field_validator("name")
    @classmethod
    def mask_name(cls, v: str) -> str:
        """名称脱敏：只保留首字，其余替换为*"""
        if len(v) <= 1:
            return v
        return v[0] + "*" * (len(v) - 1)


class UserListItem(ORMModel):
    """用户列表项（admin视角）"""
    id: int
    email: str
    name: str
    role: str
    daily_quota: int
    quota_used: int
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
