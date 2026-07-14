"""
FastAPI 依赖注入 - 认证/授权/数据库/分页
对齐阶段三安全合规基线: JWT + API Key + RBAC 三级体系
"""

from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.security import (
    TokenBlacklist,
    decode_token,
    extract_bearer_token,
    hash_api_key,
)
from app.db.session import get_db
from app.models.user import APIKey, User, UserRole
from app.schemas.common import PaginationParams

# === 数据库依赖 ===
DBSession = Annotated[AsyncSession, Depends(get_db)]


# === 分页依赖 ===

def get_pagination(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> PaginationParams:
    """分页参数依赖"""
    return PaginationParams(page=page, page_size=page_size)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]


# === JWT 认证依赖 ===

async def get_current_user_from_jwt(
    db: DBSession,
    authorization: str | None = Header(default=None),
) -> User:
    """
    从JWT令牌解析当前用户
    流程: 提取Bearer token → 解码JWT → 检查黑名单 → 查询用户 → 验证活跃状态
    """
    # 1. 提取令牌
    token = extract_bearer_token(authorization or "")
    if not token:
        raise AuthError.token_invalid()

    # 2. 解码JWT
    from jose import JWTError
    try:
        payload = decode_token(token)
    except JWTError as exc:
        # 区分过期和其他无效
        if "expired" in str(exc).lower():
            raise AuthError.token_expired()
        raise AuthError.token_invalid()

    # 3. 验证令牌类型
    if payload.get("type") != "access":
        raise AuthError.token_invalid()

    # 4. 检查黑名单
    jti = payload.get("jti", "")
    if jti and await TokenBlacklist.is_blacklisted(jti):
        raise AuthError.token_invalid()

    # 5. 查询用户
    user_id = int(payload.get("sub", 0))
    if user_id <= 0:
        raise AuthError.token_invalid()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthError.token_invalid()

    # 6. 验证账户状态
    if not user.is_active:
        raise AuthError.token_invalid()

    return user


CurrentUser = Annotated[User, Depends(get_current_user_from_jwt)]


# === API Key 认证依赖 ===

async def get_current_user_from_api_key(
    db: DBSession,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    """
    从API Key解析当前用户
    流程: 提取X-API-Key → SHA-256哈希 → 查库验证 → 检查过期/活跃 → 更新last_used_at
    """
    if not x_api_key:
        raise AuthError.api_key_invalid()

    # 哈希后查询
    key_hash = hash_api_key(x_api_key)
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,  # noqa: E712
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise AuthError.api_key_invalid()

    # 检查过期
    if api_key.is_expired:
        raise AuthError.api_key_expired()

    # 查询关联用户
    result = await db.execute(
        select(User).where(User.id == api_key.user_id)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthError.api_key_invalid()

    # 异步更新最后使用时间（不阻塞请求）
    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    api_key.last_used_at = datetime.now(CST)
    await db.flush()

    return user


# === 复合认证依赖 (JWT 或 API Key) ===

async def get_current_user(
    db: DBSession,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    """
    复合认证: 优先JWT，其次API Key
    两种方式任一通过即可
    """
    # 优先JWT
    if authorization:
        return await get_current_user_from_jwt(db, authorization=authorization)

    # 其次API Key
    if x_api_key:
        return await get_current_user_from_api_key(db, x_api_key=x_api_key)

    # 都没有
    raise AuthError.token_invalid()


AnyUser = Annotated[User, Depends(get_current_user)]


# === RBAC 角色权限依赖 ===

def require_role(*required_roles: UserRole):
    """
    角色权限检查依赖工厂
    用法: @router.get(..., dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    required_values = {r.value for r in required_roles}

    async def _check(current_user: CurrentUser) -> User:
        if current_user.role not in required_values:
            role_names = " / ".join(r.value for r in required_roles)
            raise AuthError.permission_denied(role_names)
        return current_user

    return _check


def require_admin() -> Annotated[User, Depends]:
    """要求管理员权限"""
    return Annotated[User, Depends(require_role(UserRole.ADMIN))]


def require_analyst_or_above() -> Annotated[User, Depends]:
    """要求分析师或管理员权限"""
    return Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]
