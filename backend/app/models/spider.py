"""
爬虫任务数据模型 - 对齐设计文档 ER图 & 数据字典
表: spider_tasks
安全分级: 大部分=内部，result=公开
"""

from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CST = timezone(timedelta(hours=8))


class TaskType(str, Enum):
    """爬虫任务类型"""
    WEB = "web"              # Web流量数据 (SimilarWeb等)
    APP = "app"              # App下载/收入数据
    SENTIMENT = "sentiment"  # 舆情数据采集
    PRICING = "pricing"      # 定价信息采集
    MODEL_RANK = "model_rank" # 模型能力排名


class TaskStatus(str, Enum):
    """爬虫任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class SpiderTask(Base):
    """
    爬虫任务表 - 对齐设计文档§4.5数据字典
    设计: 使用字符串主键（task_前缀），方便分布式追踪
    """
    __tablename__ = "spider_tasks"

    # 覆盖Base的id字段 - 使用字符串主键
    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="任务ID，task_前缀",
    )
    competitor_slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="目标竞品slug",
    )
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="任务类型: web/app/sentiment/pricing/model_rank",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING.value,
        index=True,
        comment="状态: pending/running/success/failed",
    )
    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="爬取结果JSON",
    )
    error_msg: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="失败原因",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始执行时间",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )

    def __repr__(self) -> str:
        return f"<SpiderTask(id={self.id}, type={self.task_type}, status={self.status})>"

    @property
    def duration_seconds(self) -> float | None:
        """任务执行耗时（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self.status in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value)
