"""
审计日志数据模型 - 对齐设计文档 ER图 & 安全合规基线
表: audit_logs
安全分级: 内部（含用户行为轨迹，需严格访问控制）
"""

from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """
    审计日志表 - 对齐设计文档§3 ER图
    安全等级: 内部（含用户行为轨迹）
    用途: 合规审计、安全追溯、操作回放
    """
    __tablename__ = "audit_logs"

    # 覆盖Base的id字段 - 使用自增ID
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="日志ID",
    )
    request_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="请求ID（与X-Request-ID头一致）",
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="用户ID（未认证请求为NULL）",
    )
    user_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="用户邮箱（脱敏日志用）",
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="HTTP方法: GET/POST/PUT/DELETE",
    )
    path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="请求路径",
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="HTTP响应状态码",
    )
    client_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="客户端IP（IPv4/IPv6）",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User-Agent",
    )
    cost_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="本次请求消耗的配额",
    )
    response_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="响应时间（毫秒）",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="错误码（如果有）",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, request_id={self.request_id}, "
            f"method={self.method}, path={self.path}, status={self.status_code})>"
        )
