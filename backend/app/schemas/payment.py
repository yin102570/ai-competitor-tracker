"""
支付系统Schema - 充值订单、套餐、回调验签
Pydantic v2，ConfigDict(from_attributes=True)

接口契约:
  CreateOrderRequest  -> POST /payment/orders
  CreateOrderResponse <- 创建充值订单响应
  OrderStatusResponse <- GET  /payment/orders/{order_id}
  PaymentPlanResponse <- GET  /payment/plans
  WechatCallbackRequest  -> POST /payment/callback/wechat
  AlipayCallbackRequest  -> POST /payment/callback/alipay
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel


# ============================================================
# 套餐
# ============================================================

class PaymentPlanResponse(ORMModel):
    """套餐列表响应项"""
    id: int
    plan_type: str = Field(..., description="套餐类型: trial/standard/professional/enterprise")
    name: str = Field(..., description="套餐名称")
    price: float = Field(..., description="套餐价格（元）")
    quota: int = Field(..., description="基础查询配额次数")
    description: str = Field("", description="套餐描述")
    bonus: int = Field(0, description="赠送查询次数")
    discount: float = Field(1.0, description="折扣率")
    total_quota: int = Field(..., description="实际可用配额（基础+赠送）")
    is_active: bool = Field(True, description="是否在售")


# ============================================================
# 创建订单
# ============================================================

class CreateOrderRequest(BaseModel):
    """创建充值订单请求"""
    plan_type: str = Field(
        ...,
        description="套餐类型: trial/standard/professional/enterprise",
        pattern="^(trial|standard|professional|enterprise)$",
    )
    channel: str = Field(
        default="wechat",
        description="支付渠道: wechat/alipay",
        pattern="^(wechat|alipay)$",
    )


class CreateOrderResponse(BaseModel):
    """创建充值订单响应"""
    model_config = ConfigDict(from_attributes=True)

    order_no: str = Field(..., description="业务订单号")
    plan_type: str = Field(..., description="套餐类型")
    plan_name: str = Field(..., description="套餐名称")
    amount: float = Field(..., description="实付金额（元）")
    quota_granted: int = Field(..., description="本单授予配额次数")
    channel: str = Field(..., description="支付渠道")
    status: str = Field(..., description="订单状态")
    # 支付参数 - 由第三方支付SDK生成，前端拉起支付使用
    pay_params: dict[str, Any] = Field(
        default_factory=dict,
        description="拉起支付所需参数（预支付token/二维码链接等）",
    )
    created_at: datetime = Field(..., description="下单时间")


# ============================================================
# 订单状态查询
# ============================================================

class OrderStatusResponse(ORMModel):
    """订单状态查询响应"""
    order_no: str = Field(..., description="业务订单号")
    user_id: int = Field(..., description="用户ID")
    plan_type: str = Field(..., description="套餐类型")
    amount: float = Field(..., description="实付金额")
    quota_granted: int = Field(..., description="授予配额次数")
    channel: str = Field(..., description="支付渠道")
    status: str = Field(..., description="订单状态: pending/paid/cancelled/refunded")
    wechat_trade_no: str | None = Field(None, description="微信交易号")
    alipay_trade_no: str | None = Field(None, description="支付宝交易号")
    created_at: datetime = Field(..., description="下单时间")
    paid_at: datetime | None = Field(None, description="支付时间")
    refunded_at: datetime | None = Field(None, description="退款时间")


# ============================================================
# 支付回调验签 - 微信支付
# ============================================================

class WechatCallbackRequest(BaseModel):
    """
    微信支付回调请求体
    微信v3 API以JSON格式回调，需验签（签名头 + 证书序列号 + 解密报文）
    此Schema仅做结构声明，原始字节流在endpoint中先验签再解析
    """
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="微信通知ID")
    create_time: str = Field(..., description="通知创建时间 RFC3339")
    event_type: str = Field(..., description="事件类型，如 TRANSACTION.SUCCESS")
    resource_type: str = Field(default="encrypt-resource")
    resource: dict[str, Any] = Field(..., description="加密资源（ciphertext/nonce/associated_data）")


class WechatCallbackDecrypted(BaseModel):
    """微信回调解密后的支付结果（用于业务处理）"""
    model_config = ConfigDict(extra="allow")

    out_trade_no: str = Field(..., description="商户订单号（业务order_no）")
    transaction_id: str = Field(..., description="微信支付订单号")
    trade_state: str = Field(..., description="交易状态: SUCCESS/REFUND/NOTPAY/CLOSED")
    amount: dict[str, Any] = Field(default_factory=dict, description="金额信息")


class WechatCallbackResponse(BaseModel):
    """微信回调响应（微信要求返回指定格式）"""
    code: str = Field(default="SUCCESS", description="处理结果码，SUCCESS表示已正确处理")
    message: str = Field(default="", description="错误原因（非SUCCESS时填写）")


# ============================================================
# 支付回调验签 - 支付宝
# ============================================================

class AlipayCallbackRequest(BaseModel):
    """
    支付宝异步回调请求体
    支付宝以 application/x-www-form-urlencoded 回调，FastAPI会解析为dict
    验签使用支付宝公钥对 sign/sign_type 字段校验
    """
    model_config = ConfigDict(extra="allow")

    trade_no: str = Field(..., description="支付宝交易号")
    out_trade_no: str = Field(..., description="商户订单号（业务order_no）")
    trade_status: str = Field(
        ...,
        description="交易状态: TRADE_SUCCESS/TRADE_FINISHED/WAIT_BUYER_PAY",
    )
    total_amount: str = Field(..., description="订单金额（元，字符串）")
    app_id: str = Field(..., description="支付宝应用ID")
    sign: str = Field(..., description="签名")
    sign_type: str = Field(default="RSA2", description="签名类型")
    notify_id: str = Field(..., description="通知ID")
    seller_id: str = Field(..., description="卖家支付宝用户号")


class AlipayCallbackResponse(BaseModel):
    """支付宝回调响应（返回纯文本 success/failure）"""
    success: bool = Field(default=True, description="是否处理成功")


# ============================================================
# 退款
# ============================================================

class RefundRequest(BaseModel):
    """退款请求（内部/管理端调用）"""
    order_no: str = Field(..., description="业务订单号")
    reason: str = Field(default="", max_length=500, description="退款原因")


class RefundResponse(BaseModel):
    """退款响应"""
    model_config = ConfigDict(from_attributes=True)

    order_no: str = Field(..., description="业务订单号")
    status: str = Field(..., description="退款后订单状态")
    refunded_at: datetime = Field(..., description="退款完成时间")
