"""
竞品数据模型 - 对齐设计文档 ER图 & 数据字典
表: competitors, competitor_history
安全分级: 公开 / 内部
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CST = timezone(timedelta(hours=8))


class Competitor(Base):
    """
    竞品主表 - 对齐设计文档§4.3数据字典
    安全等级: slug/name/company/category/logo_url/website/pricing_info = 公开
    """
    __tablename__ = "competitors"

    # Override Base.id - slug 作为业务主键，id 降级为普通字段
    id: Mapped[int | None] = mapped_column(
        primary_key=False,
        autoincrement=False,
        nullable=True,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        comment="URL友好标识，如 chatgpt",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="产品名称",
    )
    company: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="所属公司",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="分类: chatbot/multimodal/search/coding",
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Logo图片URL",
    )
    website: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="官网地址",
    )
    pricing_info: Mapped[dict | None] = mapped_column(
        Text,
        nullable=True,
        comment="定价信息结构化JSON",
    )

    # 关联关系
    history: Mapped[list["CompetitorHistory"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CompetitorHistory.date.desc()",
    )

    def __repr__(self) -> str:
        return f"<Competitor(slug={self.slug}, name={self.name})>"


class CompetitorHistory(Base):
    """
    竞品历史数据表 - 对齐设计文档§4 (ER图 competitor_history)
    安全等级: 公开
    用于存储每日快照，支撑趋势分析
    """
    __tablename__ = "competitor_history"

    competitor_slug: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("competitors.slug", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联竞品slug",
    )
    date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        comment="数据日期",
    )
    monthly_visits: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="月度访问量（估算）",
    )
    ios_downloads: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="iOS下载量",
    )
    android_downloads: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Android下载量",
    )
    arena_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Chatbot Arena评分",
    )
    arena_rank: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Chatbot Arena排名",
    )

    # 关联
    competitor: Mapped["Competitor"] = relationship(back_populates="history")

    def __repr__(self) -> str:
        return f"<CompetitorHistory(slug={self.competitor_slug}, date={self.date})>"
