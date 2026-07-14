"""
支付系统数据模型 - 按量计费充值模块
表: payment_plans, payment_orders
安全分级: 敏感（含交易流水号、金额）

商业模式: ¥0.5/次查询，用户充值后按量扣费
预设套餐: 体验版/标准版/专业版/企业版
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

CST = timezone(timedelta(hours=8))


# ============================================================
# 枚举定义
# ============================================================

class PaymentPlanType(str, Enum):
    """套餐类型枚举"""
    TRIAL = "trial"        # 体验版
    STANDARD = "standard"  # 标准版
    PROFESSIONAL = "professional"  # 专业版
    ENTERPRISE = "enterprise"      # 企业版


class PaymentStatus(str, Enum):
    """
    订单状态枚举 - 状态机流转
    pending  -> paid      正常支付成功
    pending  -> cancelled 用户取消 / 超时关闭
    paid     -> refunded  退款成功
    """
    PENDING = "pending"      # 待支付
    PAID = "paid"            # 已支付
    CANCELLED = "cancelled"  # 已取消
    REFUNDED = "refunded"    # 已退款


class PaymentChannel(str, Enum):
    """支付渠道枚举"""
    WECHAT = "wechat"  # 微信支付
    ALIPAY = "alipay"  # 支付宝


# ============================================================
# 预设套餐常量（用于初始化 payment_plans 表）
# ============================================================

PRESET_PLANS: list[dict[str, Any]] = [
    {
        "plan_type": PaymentPlanType.TRIAL.value,
        "name": "体验版",
        "price": 10.0,
        "quota": 20,
        "description": "适合首次体验，¥10 充 20 次查询",
        "bonus": 0,
        "discount": 1.0,
    },
    {
        "plan_type": PaymentPlanType.STANDARD.value,
        "name": "标准版",
        "price": 50.0,
        "quota": 120,
        "description": "性价比之选，¥50 充 120 次查询（赠送 20 次）",
        "bonus": 20,
        "discount": 0.95,
    },
    {
        "plan_type": PaymentPlanType.PROFESSIONAL.value,
        "name": "专业版",
        "price": 200.0,
        "quota": 500,
        "description": "专业用户首选，¥200 充 500 次查询（赠送 100 次）",
        "bonus": 100,
        "discount": 0.9,
    },
    {
        "plan_type": PaymentPlanType.ENTERPRISE.value,
        "name": "企业版",
        "price": 1000.0,
        "quota": 3000,
        "description": "企业级方案，¥1000 充 3000 次查询（赠送 1000 次）",
        "bonus": 1000,
        "discount": 0.8,
    },
]

# 单次查询单价（¥/次）- 用于配额换算
QUERY_UNIT_PRICE = 0.5


# ============================================================
# ORM 模型
# ============================================================

class PaymentPlan(Base):
    """
    充值套餐定义表
    安全等级: 公开（套餐信息可对外展示）
    预置4档: 体验版/标准版/专业版/企业版
    """
    __tablename__ = "payment_plans"

    plan_type: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
        comment="套餐类型: trial/standard/professional/enterprise",
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="套餐显示名称",
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="套餐价格（元）",
    )
    quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="基础查询配额次数",
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        comment="套餐描述",
    )
    bonus: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="额外赠送查询次数",
    )
    discount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="折扣率（1.0=原价，0.9=九折）",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="套餐是否在售",
    )

    # 关联关系
    orders: Mapped[list["PaymentOrder"]] = relationship(
        back_populates="plan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PaymentPlan(type={self.plan_type}, name={self.name}, price={self.price})>"

    @property
    def total_quota(self) -> int:
        """实际可用配额 = 基础配额 + 赠送次数"""
        return self.quota + self.bonus


class PaymentOrder(Base):
    """
    充值订单表
    安全等级: 敏感（含交易流水号、金额）
    生命周期: pending -> paid -> (refunded)
    """
    __tablename__ = "payment_orders"

    # 订单号（业务唯一，对外暴露）
    order_no: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="业务订单号，格式 PAY{yyyyMMdd}{random}",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="下单用户ID",
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("payment_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="购买的套餐ID",
    )
    plan_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="套餐类型快照（下单时冗余，便于查询统计）",
    )
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="实付金额（元）",
    )
    quota_granted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="本单实际授予的查询配额次数",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentChannel.WECHAT.value,
        comment="支付渠道: wechat/alipay",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        index=True,
        comment="订单状态: pending/paid/cancelled/refunded",
    )
    wechat_trade_no: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="微信支付交易号（微信侧返回）",
    )
    alipay_trade_no: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="支付宝交易号（支付宝侧返回）",
    )
    # Base 已提供 created_at / updated_at，此处补充支付/退款时间
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付完成时间",
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="退款完成时间",
    )
    # 额外上下文（如回调原始报文摘要、退款原因等）
    extra: Mapped[dict | None] = mapped_column(
        Text,
        nullable=True,
        comment="扩展信息JSON（回调原始数据/退款原因等）",
    )

    # 关联关系
    user: Mapped["User"] = relationship()
    plan: Mapped["PaymentPlan"] = relationship(back_populates="orders")

    def __repr__(self) -> str:
        return (
            f"<PaymentOrder(order_no={self.order_no}, user_id={self.user_id}, "
            f"amount={self.amount}, status={self.status})>"
        )

    @property
    def is_paid(self) -> bool:
        return self.status == PaymentStatus.PAID.value

    @property
    def is_pending(self) -> bool:
        return self.status == PaymentStatus.PENDING.value

    @property
    def is_refunded(self) -> bool:
        return self.status == PaymentStatus.REFUNDED.value
