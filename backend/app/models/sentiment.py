"""
舆情数据模型 - 对齐设计文档 ER图 & 数据字典
表: sentiment_records
安全分级: content=敏感(已脱敏), 其余=公开
"""

from sqlalchemy import String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SentimentRecord(Base):
    """
    舆情记录表 - 对齐设计文档§4.4数据字典
    安全等级: content=敏感(已脱敏处理), 其余=公开
    """
    __tablename__ = "sentiment_records"

    competitor_slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="关联竞品slug",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="来源: twitter/reddit/微博/知乎/即刻",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="原始内容（已PII脱敏）",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="内容SHA256哈希，去重用",
    )
    sentiment_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="情感得分 -1.0 ~ +1.0",
    )
    sentiment_label: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="neutral",
        comment="positive/neutral/negative",
    )
    topics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="提取话题标签 JSON",
    )
    published_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="原始发布时间",
    )

    def __repr__(self) -> str:
        return (
            f"<SentimentRecord(id={self.id}, slug={self.competitor_slug}, "
            f"label={self.sentiment_label}, score={self.sentiment_score:.2f})>"
        )
