"""
认证业务逻辑层 - 隔离数据访问与API路由
职责: 登录验证、令牌刷新、登出吊销、API Key CRUD
异常处理: 所有业务异常使用 AppException 体系
资源管理: 数据库会话由依赖注入管理，本层不手动关闭
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, BusinessError, NotFoundError
from app.core.security import (
    TokenBlacklist,
    create_refresh_token,
    create_token_pair,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.models.user import APIKey, User
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreatedResponse,
    APIKeyResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)

CST = timezone(timedelta(hours=8))


class AuthService:
    """认证服务 - 所有方法均为async，接收db session"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 登录
    # ============================================================

    async def login(self, request: LoginRequest) -> tuple[TokenResponse, UserResponse]:
        """
        用户登录
        流程: 查询用户 → 验证密码 → 检查账户状态 → 更新登录时间 → 生成令牌对
        返回: (TokenResponse, UserResponse)
        """
        # 查询用户
        result = await self.db.execute(
            select(User).where(User.email == request.email)
        )
        user = result.scalar_one_or_none()

        # 用户不存在或密码错误 - 统一返回相同错误避免枚举攻击
        if user is None or not verify_password(request.password, user.password_hash):
            raise AuthError.invalid_credentials()

        # 检查账户状态
        if not user.is_active:
            raise AuthError.invalid_credentials()

        # 更新登录时间
        user.last_login_at = datetime.now(CST)
        await self.db.flush()

        # 生成令牌对
        access_token, refresh_token, expires_in = create_token_pair(
            user.id, user.role
        )

        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

        user_response = UserResponse.model_validate({
            **user.__dict__,
            "quota_remaining": user.quota_remaining,
        })

        return token_response, user_response

    # ============================================================
    # 刷新令牌
    # ============================================================

    async def refresh_token(self, request: RefreshTokenRequest) -> TokenResponse:
        """
        刷新访问令牌
        流程: 解码refresh_token → 验证类型 → 检查黑名单 → 查询用户 → 生成新令牌对
        """
        try:
            payload = decode_token(request.refresh_token)
        except JWTError as exc:
            if "expired" in str(exc).lower():
                raise AuthError.token_expired()
            raise AuthError.token_invalid()

        # 验证令牌类型
        if payload.get("type") != "refresh":
            raise AuthError.token_invalid()

        # 检查黑名单
        jti = payload.get("jti", "")
        if jti and await TokenBlacklist.is_blacklisted(jti):
            raise AuthError.token_invalid()

        # 查询用户
        user_id = int(payload.get("sub", 0))
        if user_id <= 0:
            raise AuthError.token_invalid()

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise AuthError.token_invalid()

        # 生成新令牌对
        access_token, new_refresh_token, expires_in = create_token_pair(
            user.id, user.role
        )

        # 旧refresh_token加入黑名单（防止重放）
        remaining_ttl = int(
            (datetime.fromtimestamp(payload["exp"], tz=CST) - datetime.now(CST)).total_seconds()
        )
        if remaining_ttl > 0 and jti:
            await TokenBlacklist.add(jti, remaining_ttl)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
        )

    # ============================================================
    # 登出
    # ============================================================

    async def logout(self, access_token: str) -> None:
        """
        登出 - 将当前access_token加入黑名单
        TTL设为令牌剩余有效期，过期后自动清除
        """
        try:
            payload = decode_token(access_token)
        except JWTError:
            # 即使令牌无效也视为登出成功（幂等操作）
            return

        jti = payload.get("jti", "")
        if not jti:
            return

        # 计算剩余TTL
        exp = payload.get("exp")
        if exp:
            remaining_ttl = int(
                (datetime.fromtimestamp(exp, tz=CST) - datetime.now(CST)).total_seconds()
            )
            if remaining_ttl > 0:
                await TokenBlacklist.add(jti, remaining_ttl)

    # ============================================================
    # API Key 管理
    # ============================================================

    async def create_api_key(
        self,
        user_id: int,
        request: APIKeyCreateRequest,
    ) -> APIKeyCreatedResponse:
        """
        创建API Key
        流程: 生成密钥 → 哈希存储 → 返回明文（仅一次）
        安全: 明文不存储，仅返回一次
        """
        plaintext_key, key_hash, key_prefix = generate_api_key()

        # 计算过期时间
        expires_at = None
        if request.expires_in_days is not None:
            expires_at = datetime.now(CST) + timedelta(days=request.expires_in_days)

        api_key = APIKey(
            user_id=user_id,
            name=request.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(api_key)
        await self.db.flush()

        return APIKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            api_key=plaintext_key,
            key_prefix=key_prefix,
            expires_at=expires_at,
            created_at=api_key.created_at,
        )

    async def list_api_keys(self, user_id: int) -> list[APIKeyResponse]:
        """列出用户的所有API Key（不含明文）"""
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
        )
        keys = result.scalars().all()
        return [APIKeyResponse.model_validate(k) for k in keys]

    async def revoke_api_key(self, user_id: int, key_id: int) -> None:
        """
        吊销API Key（软删除 - 标记 is_active=False）
        权限校验: 只能吊销自己的Key
        """
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.user_id == user_id,
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise NotFoundError.user(key_id)

        api_key.is_active = False
        await self.db.flush()

    # ============================================================
    # 用户注册（开发环境快捷入口 - 未来扩展点）
    # ============================================================

    async def register(
        self,
        email: str,
        password: str,
        name: str,
        role: str = "viewer",
    ) -> User:
        """
        注册新用户
        扩展入口: 未来可对接邀请码/企业SSO等
        """
        # 检查邮箱唯一性
        existing = await self.db.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            raise BusinessError.duplicate("email", email)

        user = User(
            email=email,
            password_hash=hash_password(password),
            name=name,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    # ============================================================
    # 配额检查（公共方法 - 供其他模块调用）
    # ============================================================

    async def check_and_consume_quota(self, user_id: int, cost: int = 1) -> bool:
        """
        检查并消耗用户配额
        返回: True=配额充足已扣除, False=配额不足
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError.user(user_id)

        # 检查是否需要重置配额（跨天）
        now = datetime.now(CST)
        if user.quota_reset_at.date() < now.date():
            user.quota_used = 0
            user.quota_reset_at = now

        if user.is_quota_exhausted:
            raise AuthError.quota_exceeded(user.quota_used, user.daily_quota)

        user.quota_used += cost
        await self.db.flush()
        return True
