"""
支付业务逻辑层 - 充值订单创建、回调处理、退款、套餐查询
职责: 隔离支付网关交互与配额发放，确保事务安全
异常处理: 所有业务异常使用 AppException 体系
资源管理: 数据库会话由依赖注入管理，本层不手动关闭

关键安全点:
  1. 回调必须验签防伪造
  2. 配额变更使用 SELECT ... FOR UPDATE 行锁，保证事务安全
  3. 回调幂等: 已支付订单重复回调直接返回成功，不重复加配额
"""

import json
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    ErrorCode,
    NotFoundError,
)
from app.core.payment_config import (
    AlipaySigner,
    WechatSigner,
    generate_order_no,
    payment_settings,
)
from app.models.payment import (
    PRESET_PLANS,
    PaymentChannel,
    PaymentOrder,
    PaymentPlan,
    PaymentStatus,
)
from app.models.user import User
from app.schemas.payment import (
    AlipayCallbackRequest,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderStatusResponse,
    PaymentPlanResponse,
    RefundRequest,
    RefundResponse,
    WechatCallbackDecrypted,
    WechatCallbackRequest,
)

CST = timezone(timedelta(hours=8))


# ============================================================
# 支付专用异常工厂（复用 AppException + 现有错误码体系）
# ============================================================

class PaymentError:
    """支付相关异常工厂 - 复用现有 ErrorCode 体系"""

    @staticmethod
    def order_not_found(order_no: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"订单不存在: {order_no}",
            {"order_no": order_no},
        )

    @staticmethod
    def plan_not_found(plan_type: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"套餐不存在或已下架: {plan_type}",
            {"plan_type": plan_type},
        )

    @staticmethod
    def signature_invalid(channel: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"{channel} 回调验签失败，疑似伪造请求",
            {"channel": channel},
        )

    @staticmethod
    def callback_failed(detail: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"支付回调处理失败: {detail}",
        )

    @staticmethod
    def order_not_paid(order_no: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"订单未支付，无法退款: {order_no}",
            {"order_no": order_no},
        )

    @staticmethod
    def already_refunded(order_no: str) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            f"订单已退款，不可重复操作: {order_no}",
            {"order_no": order_no},
        )

    @staticmethod
    def gateway_error(channel: str, detail: str) -> AppException:
        return AppException(
            ErrorCode.INTERNAL_ERROR,
            f"{channel} 支付网关调用失败: {detail}",
        )

    @staticmethod
    def not_configured(channel: str) -> AppException:
        return AppException(
            ErrorCode.INTERNAL_ERROR,
            f"{channel} 支付未配置，请联系管理员",
        )


# ============================================================
# 支付服务
# ============================================================

class PaymentService:
    """支付服务 - 充值订单全生命周期管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 套餐查询
    # ============================================================

    async def get_plans(self) -> list[PaymentPlanResponse]:
        """
        获取在售套餐列表（公开接口）
        如表为空则自动初始化预设套餐
        """
        await self._ensure_preset_plans()

        result = await self.db.execute(
            select(PaymentPlan)
            .where(PaymentPlan.is_active == True)  # noqa: E712
            .order_by(PaymentPlan.price.asc())
        )
        plans = result.scalars().all()
        return [self._plan_to_response(p) for p in plans]

    async def get_plan_by_type(self, plan_type: str) -> PaymentPlan:
        """根据套餐类型获取套餐，不存在则抛异常"""
        await self._ensure_preset_plans()
        result = await self.db.execute(
            select(PaymentPlan).where(
                PaymentPlan.plan_type == plan_type,
                PaymentPlan.is_active == True,  # noqa: E712
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise PaymentError.plan_not_found(plan_type)
        return plan

    # ============================================================
    # 创建充值订单
    # ============================================================

    async def create_order(
        self,
        request: CreateOrderRequest,
        current_user: User,
    ) -> CreateOrderResponse:
        """
        创建充值订单
        流程: 校验套餐 -> 生成订单号 -> 落库 pending -> 调用支付网关预下单 -> 返回支付参数
        """
        # 1. 校验套餐
        plan = await self.get_plan_by_type(request.plan_type)

        # 2. 计算实付金额（折扣后）
        amount = round(plan.price * plan.discount, 2)
        quota_granted = plan.total_quota

        # 3. 生成订单号
        order_no = generate_order_no("PAY")

        # 4. 创建订单记录
        order = PaymentOrder(
            order_no=order_no,
            user_id=current_user.id,
            plan_id=plan.id,
            plan_type=plan.plan_type,
            amount=amount,
            quota_granted=quota_granted,
            channel=request.channel,
            status=PaymentStatus.PENDING.value,
        )
        self.db.add(order)
        await self.db.flush()

        # 5. 调用支付网关预下单，获取支付参数
        pay_params = await self._prepay(order, plan)

        return CreateOrderResponse(
            order_no=order.order_no,
            plan_type=order.plan_type,
            plan_name=plan.name,
            amount=order.amount,
            quota_granted=order.quota_granted,
            channel=order.channel,
            status=order.status,
            pay_params=pay_params,
            created_at=order.created_at,
        )

    # ============================================================
    # 查询订单状态
    # ============================================================

    async def query_order(
        self,
        order_no: str,
        current_user: User,
    ) -> OrderStatusResponse:
        """
        查询订单状态
        权限: 仅订单所属用户可查
        """
        order = await self._get_order_by_no(order_no)

        if order.user_id != current_user.id and not current_user.is_admin:
            raise PaymentError.order_not_found(order_no)

        return OrderStatusResponse.model_validate(order)

    # ============================================================
    # 微信支付回调处理
    # ============================================================

    async def handle_wechat_callback(
        self,
        raw_body: str,
        timestamp: str,
        nonce: str,
        signature: str,
    ) -> bool:
        """
        微信支付回调处理
        流程: 验签 -> 解密报文 -> 幂等检查 -> 更新订单 -> 加配额(行锁)
        参数:
            raw_body:   原始请求体（JSON字符串，验签用）
            timestamp:  微信回调头 Wechatpay-Timestamp
            nonce:      微信回调头 Wechatpay-Nonce
            signature:  微信回调头 Wechatpay-Signature
        返回: True=处理成功
        """
        # 1. 验签（防伪造）
        if not payment_settings.wechat_configured:
            raise PaymentError.not_configured("微信支付")

        verified = WechatSigner.verify(timestamp, nonce, raw_body, signature)
        if not verified:
            raise PaymentError.signature_invalid("微信支付")

        # 2. 解析外层通知结构
        try:
            notify_data = json.loads(raw_body)
        except json.JSONDecodeError:
            raise PaymentError.callback_failed("回调报文JSON解析失败")

        callback = WechatCallbackRequest(**notify_data)

        # 3. 仅处理支付成功事件
        if callback.event_type != "TRANSACTION.SUCCESS":
            # 非支付成功事件，记录但不处理
            return True

        # 4. 解密加密资源
        resource = callback.resource
        decrypted = WechatSigner.decrypt_resource(
            ciphertext=resource.get("ciphertext", ""),
            nonce=resource.get("nonce", ""),
            associated_data=resource.get("associated_data", ""),
        )
        payment_result = WechatCallbackDecrypted(**decrypted)

        # 5. 幂等校验 + 加配额（事务安全）
        await self._process_payment_success(
            order_no=payment_result.out_trade_no,
            trade_no=payment_result.transaction_id,
            channel=PaymentChannel.WECHAT,
            trade_no_field="wechat_trade_no",
            extra={"wechat_callback": decrypted},
        )

        return True

    # ============================================================
    # 支付宝回调处理
    # ============================================================

    async def handle_alipay_callback(
        self,
        params: dict,
    ) -> bool:
        """
        支付宝异步回调处理
        流程: 验签 -> 幂等检查 -> 更新订单 -> 加配额(行锁)
        参数:
            params: 支付宝回调参数字典（已由FastAPI解析）
        返回: True=处理成功
        """
        # 1. 验签（防伪造）
        if not payment_settings.alipay_configured:
            raise PaymentError.not_configured("支付宝")

        sign = params.get("sign", "")
        if not sign:
            raise PaymentError.signature_invalid("支付宝")

        verified = AlipaySigner.verify(params, sign)
        if not verified:
            raise PaymentError.signature_invalid("支付宝")

        # 2. 校验 app_id 一致性
        if params.get("app_id") != payment_settings.alipay_app_id:
            raise PaymentError.callback_failed("app_id 不匹配")

        callback = AlipayCallbackRequest(**params)

        # 3. 仅处理交易成功状态
        if callback.trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return True

        # 4. 幂等校验 + 加配额（事务安全）
        await self._process_payment_success(
            order_no=callback.out_trade_no,
            trade_no=callback.trade_no,
            channel=PaymentChannel.ALIPAY,
            trade_no_field="alipay_trade_no",
            extra={"alipay_callback": params},
        )

        return True

    # ============================================================
    # 退款处理
    # ============================================================

    async def refund(
        self,
        request: RefundRequest,
        current_user: User,
    ) -> RefundResponse:
        """
        退款处理
        权限: 仅 admin 可操作
        流程: 校验订单已支付 -> 调用支付网关退款 -> 扣减配额(行锁) -> 更新订单状态
        """
        if not current_user.is_admin:
            from app.core.exceptions import AuthError
            raise AuthError.permission_denied("admin")

        order = await self._get_order_by_no(request.order_no)

        # 状态校验
        if not order.is_paid:
            raise PaymentError.order_not_paid(request.order_no)
        if order.is_refunded:
            raise PaymentError.already_refunded(request.order_no)

        # 调用支付网关退款
        await self._call_refund_gateway(order, request.reason)

        # 扣减用户配额（事务安全 - 行锁）
        await self._adjust_user_quota(
            user_id=order.user_id,
            delta=-order.quota_granted,
            order_no=order.order_no,
            action="refund",
        )

        # 更新订单状态
        order.status = PaymentStatus.REFUNDED.value
        order.refunded_at = datetime.now(CST)
        # 记录退款原因
        extra = json.loads(order.extra) if order.extra else {}
        extra["refund_reason"] = request.reason
        extra["refunded_by"] = current_user.id
        order.extra = json.dumps(extra, ensure_ascii=False)
        await self.db.flush()

        return RefundResponse(
            order_no=order.order_no,
            status=order.status,
            refunded_at=order.refunded_at,
        )

    # ============================================================
    # 内部方法 - 支付成功核心逻辑
    # ============================================================

    async def _process_payment_success(
        self,
        order_no: str,
        trade_no: str,
        channel: PaymentChannel,
        trade_no_field: str,
        extra: dict,
    ) -> None:
        """
        支付成功统一处理（幂等 + 事务安全）
        1. 查询订单（行锁）
        2. 幂等: 已支付则直接返回
        3. 更新订单状态为 paid
        4. 加配额（用户行锁）
        """
        # 1. 查询并锁定订单
        result = await self.db.execute(
            select(PaymentOrder)
            .where(PaymentOrder.order_no == order_no)
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise PaymentError.order_not_found(order_no)

        # 2. 幂等: 已支付/已退款 直接返回成功（不重复加配额）
        if order.status in (PaymentStatus.PAID.value, PaymentStatus.REFUNDED.value):
            return

        # 3. 状态校验: 仅 pending 可转 paid
        if order.status != PaymentStatus.PENDING.value:
            raise PaymentError.callback_failed(
                f"订单状态异常: {order.status}，无法置为已支付"
            )

        # 4. 更新订单
        order.status = PaymentStatus.PAID.value
        order.paid_at = datetime.now(CST)
        setattr(order, trade_no_field, trade_no)
        order.extra = json.dumps(extra, ensure_ascii=False)
        await self.db.flush()

        # 5. 加配额（用户行锁，保证事务安全）
        await self._adjust_user_quota(
            user_id=order.user_id,
            delta=order.quota_granted,
            order_no=order.order_no,
            action="recharge",
        )

    async def _adjust_user_quota(
        self,
        user_id: int,
        delta: int,
        order_no: str,
        action: str,
    ) -> None:
        """
        调整用户配额（事务安全 - SELECT FOR UPDATE 行锁）
        充值: delta > 0，增加 daily_quota
        退款: delta < 0，扣减 daily_quota（不低于0）
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError.user(user_id)

        if delta > 0:
            # 充值: 直接累加配额上限
            user.daily_quota += delta
        elif delta < 0:
            # 退款: 扣减配额上限，但不能低于已用量
            new_quota = max(user.quota_used, user.daily_quota + delta)
            user.daily_quota = new_quota

        await self.db.flush()

    # ============================================================
    # 内部方法 - 支付网关交互
    # ============================================================

    async def _prepay(
        self,
        order: PaymentOrder,
        plan: PaymentPlan,
    ) -> dict:
        """
        调用支付网关预下单，返回前端拉起支付所需参数
        开发环境/未配置时返回模拟参数，不阻塞下单流程
        """
        if order.channel == PaymentChannel.WECHAT.value:
            return await self._wechat_prepay(order, plan)
        elif order.channel == PaymentChannel.ALIPAY.value:
            return await self._alipay_prepay(order, plan)
        return {}

    async def _wechat_prepay(
        self,
        order: PaymentOrder,
        plan: PaymentPlan,
    ) -> dict:
        """微信支付 v3 统一下单（Native/JSAPI）"""
        if not payment_settings.wechat_configured:
            # 未配置 - 返回模拟参数（开发环境友好）
            return {
                "mode": "mock",
                "order_no": order.order_no,
                "amount": order.amount,
                "message": "微信支付未配置，开发环境返回模拟参数",
            }

        url = "/v3/pay/transactions/native"
        full_url = f"{payment_settings.wechat_base_url}{url}"

        body = {
            "appid": payment_settings.wechat_app_id,
            "mchid": payment_settings.wechat_mch_id,
            "description": f"AI竞品追踪 - {plan.name}",
            "out_trade_no": order.order_no,
            "notify_url": payment_settings.wechat_notify_url,
            "amount": {
                "total": int(order.amount * 100),  # 分
                "currency": "CNY",
            },
        }
        body_str = json.dumps(body, ensure_ascii=False)

        auth_header = WechatSigner.build_auth_header("POST", url, body_str)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    full_url,
                    content=body_str,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
            if resp.status_code != 200:
                raise PaymentError.gateway_error(
                    "微信支付", f"HTTP {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            # Native支付返回 code_url（二维码链接）
            return {"code_url": data.get("code_url", "")}
        except httpx.HTTPError as exc:
            raise PaymentError.gateway_error("微信支付", str(exc))

    async def _alipay_prepay(
        self,
        order: PaymentOrder,
        plan: PaymentPlan,
    ) -> dict:
        """支付宝电脑网站支付（alipay.trade.page.pay）"""
        if not payment_settings.alipay_configured:
            return {
                "mode": "mock",
                "order_no": order.order_no,
                "amount": order.amount,
                "message": "支付宝未配置，开发环境返回模拟参数",
            }

        biz_content = {
            "out_trade_no": order.order_no,
            "total_amount": f"{order.amount:.2f}",
            "subject": f"AI竞品追踪 - {plan.name}",
            "product_code": "FAST_INSTANT_TRADE_PAY",
        }

        params = {
            "app_id": payment_settings.alipay_app_id,
            "method": "alipay.trade.page.pay",
            "charset": "utf-8",
            "sign_type": payment_settings.alipay_sign_type,
            "timestamp": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "notify_url": payment_settings.alipay_notify_url,
            "biz_content": json.dumps(biz_content, ensure_ascii=False),
        }
        params["sign"] = AlipaySigner.sign(params)

        return {
            "gateway_url": payment_settings.alipay_gateway,
            "params": params,
        }

    async def _call_refund_gateway(
        self,
        order: PaymentOrder,
        reason: str,
    ) -> None:
        """调用支付网关退款接口"""
        if order.channel == PaymentChannel.WECHAT.value:
            await self._wechat_refund(order, reason)
        elif order.channel == PaymentChannel.ALIPAY.value:
            await self._alipay_refund(order, reason)

    async def _wechat_refund(self, order: PaymentOrder, reason: str) -> None:
        """微信支付 v3 退款"""
        if not payment_settings.wechat_configured:
            return  # 未配置时跳过网关调用

        if not order.wechat_trade_no:
            raise PaymentError.gateway_error("微信支付", "缺少微信交易号，无法退款")

        url = "/v3/refund/domestic/refunds"
        full_url = f"{payment_settings.wechat_base_url}{url}"

        body = {
            "transaction_id": order.wechat_trade_no,
            "out_refund_no": generate_order_no("RF"),
            "reason": reason or "用户退款",
            "amount": {
                "refund": int(order.amount * 100),
                "total": int(order.amount * 100),
                "currency": "CNY",
            },
        }
        body_str = json.dumps(body, ensure_ascii=False)
        auth_header = WechatSigner.build_auth_header("POST", url, body_str)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    full_url,
                    content=body_str,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
            if resp.status_code not in (200, 202):
                raise PaymentError.gateway_error(
                    "微信支付", f"退款失败 HTTP {resp.status_code}: {resp.text}"
                )
        except httpx.HTTPError as exc:
            raise PaymentError.gateway_error("微信支付", str(exc))

    async def _alipay_refund(self, order: PaymentOrder, reason: str) -> None:
        """支付宝退款（alipay.trade.refund）"""
        if not payment_settings.alipay_configured:
            return

        if not order.alipay_trade_no:
            raise PaymentError.gateway_error("支付宝", "缺少支付宝交易号，无法退款")

        biz_content = {
            "trade_no": order.alipay_trade_no,
            "refund_amount": f"{order.amount:.2f}",
            "refund_reason": reason or "用户退款",
            "out_request_no": generate_order_no("RF"),
        }

        params = {
            "app_id": payment_settings.alipay_app_id,
            "method": "alipay.trade.refund",
            "charset": "utf-8",
            "sign_type": payment_settings.alipay_sign_type,
            "timestamp": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": json.dumps(biz_content, ensure_ascii=False),
        }
        params["sign"] = AlipaySigner.sign(params)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    payment_settings.alipay_gateway,
                    data=params,
                )
            if resp.status_code != 200:
                raise PaymentError.gateway_error(
                    "支付宝", f"退款失败 HTTP {resp.status_code}"
                )
            data = resp.json()
            resp_data = data.get("alipay_trade_refund_response", {})
            if resp_data.get("code") != "10000":
                raise PaymentError.gateway_error(
                    "支付宝", f"{resp_data.get('sub_msg', '退款失败')}"
                )
        except httpx.HTTPError as exc:
            raise PaymentError.gateway_error("支付宝", str(exc))

    # ============================================================
    # 内部方法 - 数据查询
    # ============================================================

    async def _get_order_by_no(self, order_no: str) -> PaymentOrder:
        """根据订单号查询订单，不存在则抛异常"""
        result = await self.db.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise PaymentError.order_not_found(order_no)
        return order

    async def _ensure_preset_plans(self) -> None:
        """确保预设套餐已初始化（幂等，表为空时自动填充）"""
        result = await self.db.execute(
            select(func.count()).select_from(PaymentPlan)
        )
        count = result.scalar_one() or 0
        if count > 0:
            return

        for plan_data in PRESET_PLANS:
            plan = PaymentPlan(**plan_data)
            self.db.add(plan)
        await self.db.flush()

    @staticmethod
    def _plan_to_response(plan: PaymentPlan) -> PaymentPlanResponse:
        """PaymentPlan ORM -> PaymentPlanResponse"""
        return PaymentPlanResponse(
            id=plan.id,
            plan_type=plan.plan_type,
            name=plan.name,
            price=plan.price,
            quota=plan.quota,
            description=plan.description,
            bonus=plan.bonus,
            discount=plan.discount,
            total_quota=plan.total_quota,
            is_active=plan.is_active,
        )
