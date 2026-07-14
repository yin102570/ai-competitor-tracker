"""
支付系统API路由 - 充值套餐、订单创建、回调验签
路由前缀: /api/v1/payment

接口清单:
  GET  /plans                     获取套餐列表（公开）
  POST /orders                    创建充值订单（需认证）
  GET  /orders/{order_no}         查询订单状态（需认证）
  POST /callback/wechat           微信支付回调（公开，验签）
  POST /callback/alipay           支付宝回调（公开，验签）
  POST /refund                    退款处理（admin only）
"""

from fastapi import APIRouter, Request, status
from fastapi.responses import PlainTextResponse

from app.core.deps import AnyUser, DBSession
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderStatusResponse,
    PaymentPlanResponse,
    RefundRequest,
    RefundResponse,
    WechatCallbackResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payment", tags=["支付系统"])


# ============================================================
# 套餐列表（公开）
# ============================================================

@router.get(
    "/plans",
    response_model=list[PaymentPlanResponse],
    status_code=status.HTTP_200_OK,
    summary="获取充值套餐列表",
    description="获取所有在售充值套餐，无需认证。¥0.5/次查询，充值后按量扣费",
)
async def get_plans(
    db: DBSession,
) -> list[PaymentPlanResponse]:
    """获取套餐列表"""
    service = PaymentService(db)
    return await service.get_plans()


# ============================================================
# 创建充值订单（需认证）
# ============================================================

@router.post(
    "/orders",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建充值订单",
    description="选择套餐和支付渠道，创建充值订单并返回支付参数",
)
async def create_order(
    request: CreateOrderRequest,
    db: DBSession,
    current_user: AnyUser,
) -> CreateOrderResponse:
    """创建充值订单"""
    service = PaymentService(db)
    return await service.create_order(request, current_user)


# ============================================================
# 查询订单状态（需认证）
# ============================================================

@router.get(
    "/orders/{order_no}",
    response_model=OrderStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="查询订单状态",
    description="查询指定订单的支付状态、金额、配额等信息",
)
async def query_order(
    order_no: str,
    db: DBSession,
    current_user: AnyUser,
) -> OrderStatusResponse:
    """查询订单状态"""
    service = PaymentService(db)
    return await service.query_order(order_no, current_user)


# ============================================================
# 微信支付回调（公开，验签）
# ============================================================

@router.post(
    "/callback/wechat",
    response_model=WechatCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="微信支付回调",
    description="微信支付异步通知回调接口，自动验签+加配额。无需认证，但必须验签防伪造",
)
async def wechat_callback(
    request: Request,
    db: DBSession,
) -> WechatCallbackResponse:
    """
    微信支付回调
    从请求头提取验签参数，原始报文用于验签
    """
    # 提取微信验签头
    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    signature = request.headers.get("Wechatpay-Signature", "")

    # 获取原始报文（验签必须用原始字节，不能重新序列化）
    raw_body = (await request.body()).decode("utf-8")

    service = PaymentService(db)
    await service.handle_wechat_callback(
        raw_body=raw_body,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
    )

    return WechatCallbackResponse(code="SUCCESS", message="")


# ============================================================
# 支付宝回调（公开，验签）
# ============================================================

@router.post(
    "/callback/alipay",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
    summary="支付宝回调",
    description="支付宝异步通知回调接口，自动验签+加配额。无需认证，但必须验签防伪造。成功返回纯文本 success",
)
async def alipay_callback(
    request: Request,
    db: DBSession,
) -> str:
    """
    支付宝回调
    支付宝以 application/x-www-form-urlencoded 回调
    成功需返回纯文本 "success"，否则支付宝会重试
    """
    # 解析表单参数
    form_data = await request.form()
    params = {k: v for k, v in form_data.items()}

    service = PaymentService(db)
    success = await service.handle_alipay_callback(params)

    return "success" if success else "failure"


# ============================================================
# 退款处理（admin only）
# ============================================================

@router.post(
    "/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_200_OK,
    summary="订单退款",
    description="对已支付订单发起退款，自动扣减配额并调用支付网关退款。仅管理员可操作",
)
async def refund_order(
    request: RefundRequest,
    db: DBSession,
    current_user: AnyUser,
) -> RefundResponse:
    """订单退款"""
    service = PaymentService(db)
    return await service.refund(request, current_user)
