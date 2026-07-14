"""
安全核心 - JWT令牌 / 密码哈希 / API Key 生成与验证
对齐阶段三安全合规基线文档

设计要点:
- JWT: HS256签名，access+refresh双令牌，Redis黑名单
- 密码: bcrypt哈希（passlib），成本因子12
- API Key: secrets.token_urlsafe生成，SHA-256哈希存储
- 所有密钥从环境变量注入，严禁硬编码
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# 时区
CST = timezone(timedelta(hours=8))

# 密码哈希上下文 - bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


# ============================================================
# 密码安全
# ============================================================

def hash_password(password: str) -> str:
    """对明文密码进行bcrypt哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希是否匹配
    使用恒定时间比较，防止时序攻击
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# ============================================================
# JWT 令牌
# ============================================================

def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """
    创建访问令牌
    返回: (token, jti) — jti用于黑名单管理
    """
    jti = uuid.uuid4().hex
    expire = datetime.now(CST) + (
        expires_delta
        or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "jti": jti,
        "type": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def create_refresh_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """
    创建刷新令牌
    返回: (token, jti)
    """
    jti = uuid.uuid4().hex
    expire = datetime.now(CST) + (
        expires_delta
        or timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "jti": jti,
        "type": "refresh",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    解码JWT令牌，验证签名和过期时间
    异常时抛出 JWTError
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def create_token_pair(user_id: int, role: str) -> tuple[str, str, int]:
    """
    创建令牌对（access + refresh）
    返回: (access_token, refresh_token, expires_in_seconds)
    """
    access_token, _ = create_access_token(user_id, role)
    refresh_token, _ = create_refresh_token(user_id, role)
    expires_in = settings.jwt_access_token_expire_minutes * 60
    return access_token, refresh_token, expires_in


# ============================================================
# API Key 安全
# ============================================================

def generate_api_key() -> tuple[str, str, str]:
    """
    生成API Key
    返回: (plaintext_key, key_hash, key_prefix)
    - plaintext_key: 明文密钥（仅返回一次）
    - key_hash: SHA-256哈希（存储用）
    - key_prefix: 前8位（展示用）
    """
    raw = secrets.token_urlsafe(settings.api_key_length)
    plaintext_key = f"{settings.api_key_prefix}{raw}"
    key_hash = hash_api_key(plaintext_key)
    key_prefix = plaintext_key[:8]
    return plaintext_key, key_hash, key_prefix


def hash_api_key(api_key: str) -> str:
    """对API Key进行SHA-256哈希"""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def extract_bearer_token(authorization: str) -> str | None:
    """
    从 Authorization 头提取 Bearer token
    格式: "Bearer <token>"
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


# ============================================================
# Redis 令牌黑名单
# ============================================================

class TokenBlacklist:
    """
    JWT令牌黑名单 - 基于Redis
    登出时将jti加入黑名单，TTL与令牌剩余有效期一致
    """

    _redis = None

    @classmethod
    async def _get_redis(cls):
        """延迟初始化Redis连接"""
        if cls._redis is None:
            import redis.asyncio as aioredis
            cls._redis = aioredis.from_url(
                settings.redis_url,
                db=settings.redis_token_blacklist_db,
                decode_responses=True,
            )
        return cls._redis

    @classmethod
    async def add(cls, jti: str, ttl_seconds: int) -> None:
        """将令牌jti加入黑名单"""
        try:
            redis = await cls._get_redis()
            await redis.setex(f"blacklist:{jti}", ttl_seconds, "1")
        except Exception:
            pass  # Redis不可用时静默降级

    @classmethod
    async def is_blacklisted(cls, jti: str) -> bool:
        """检查令牌是否在黑名单中（Redis不可用时降级返回False）"""
        try:
            redis = await cls._get_redis()
            result = await redis.get(f"blacklist:{jti}")
            return result is not None
        except Exception:
            return False

    @classmethod
    async def close(cls) -> None:
        """关闭Redis连接"""
        if cls._redis is not None:
            await cls._redis.close()
            cls._redis = None
