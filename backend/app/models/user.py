"""
用户与认证数据模型 - 对齐阶段四设计文档 §5 ER图 & 数据字典
表: users, api_keys
安全分级: 内部 / 敏感
"""

from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CST = timezone(timedelta(hours=8))


class UserRole(str, Enum):
    """
    用户角色枚举 - RBAC三级权限模型
    admin:   系统管理员，拥有全部权限
    analyst: 数据分析师，可查看/导出数据、管理竞品
    viewer:  只读用户，仅可查看Dashboard
    """
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base):
    """
    用户表 - 对齐设计文档数据字典
    安全等级: 敏感（含邮箱、配额信息）
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="用户邮箱，唯一登录标识",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt哈希密码，不存储明文",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="用户显示名称",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.VIEWER.value,
        index=True,
        comment="RBAC角色: admin/analyst/viewer",
    )
    daily_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="每日查询配额上限",
    )
    quota_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="当日已用查询次数",
    )
    quota_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(CST),
        comment="配额重置时间（每日UTC+8 00:00重置）",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="账户是否激活",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近登录时间",
    )

    # 关联关系
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    @property
    def is_analyst_or_above(self) -> bool:
        return self.role in (UserRole.ADMIN.value, UserRole.ANALYST.value)

    @property
    def quota_remaining(self) -> int:
        """剩余配额"""
        return max(0, self.daily_quota - self.quota_used)

    @property
    def is_quota_exhausted(self) -> bool:
        """配额是否耗尽"""
        return self.quota_used >= self.daily_quota


class APIKey(Base):
    """
    API Key 表 - 对齐设计文档数据字典
    安全等级: 敏感（含密钥哈希）
    设计: 仅存储 key_hash，明文仅在创建时返回一次
    """
    __tablename__ = "api_keys"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属用户ID",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="API Key名称（用户自定义）",
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="API Key的SHA-256哈希，不存储明文",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="API Key前8位，用于展示识别",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="过期时间，NULL表示永不过期",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="API Key是否激活",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近使用时间",
    )

    # 关联关系
    user: Mapped["User"] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now(CST) >= self.expires_at
