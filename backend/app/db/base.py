"""
SQLAlchemy 2.0 异步声明基类
所有模型继承自 Base，自动获得通用字段
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 命名约定 - 确保索引/约束命名一致，便于Alembic迁移
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

CST = timezone(timedelta(hours=8))


class Base(DeclarativeBase):
    """
    所有ORM模型的基类
    提供统一的 id / created_at / updated_at 字段
    """
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(CST),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(CST),
        onupdate=lambda: datetime.now(CST),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """将模型实例转换为字典（基础实现，子类可覆写）"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
