"""
认证模块API路由 - 对齐阶段四设计文档 §4 接口契约
路由前缀: /api/v1/auth

接口清单:
  POST   /login          登录获取令牌
  POST   /refresh        刷新令牌
  POST   /logout         登出吊销令牌
  POST   /api-keys       创建API Key
  GET    /api-keys       列出API Key
  DELETE /api-keys/{id}  吊销API Key
  GET    /me             获取当前用户信息
"""

from fastapi import APIRouter, Header, status

from app.core.deps import DBSession, CurrentUser
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreatedResponse,
    APIKeyResponse,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


# ============================================================
# 登录 / 刷新 / 登出
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登录",
    description="使用邮箱密码登录，返回JWT访问令牌和刷新令牌",
)
async def login(
    request: LoginRequest,
    db: DBSession,
) -> TokenResponse:
    """登录获取令牌对"""
    service = AuthService(db)
    token_response, _ = await service.login(request)
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="刷新令牌",
    description="使用刷新令牌获取新的访问令牌",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: DBSession,
) -> TokenResponse:
    """刷新访问令牌"""
    service = AuthService(db)
    return await service.refresh_token(request)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登出",
    description="吊销当前访问令牌",
)
async def logout(
    db: DBSession,
    current_user: CurrentUser,
    authorization: str | None = Header(default=None),
) -> LogoutResponse:
    """登出并吊销令牌"""
    service = AuthService(db)
    # 从Authorization头提取token
    from app.core.security import extract_bearer_token
    token = extract_bearer_token(authorization or "")
    if token:
        await service.logout(token)
    return LogoutResponse()


# ============================================================
# API Key 管理
# ============================================================

@router.post(
    "/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建API Key",
    description="创建新的API Key，明文仅在创建时返回一次",
)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> APIKeyCreatedResponse:
    """创建API Key"""
    service = AuthService(db)
    return await service.create_api_key(current_user.id, request)


@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
    status_code=status.HTTP_200_OK,
    summary="列出API Key",
    description="列出当前用户的所有API Key（不含明文）",
)
async def list_api_keys(
    db: DBSession,
    current_user: CurrentUser,
) -> list[APIKeyResponse]:
    """列出用户的API Key"""
    service = AuthService(db)
    return await service.list_api_keys(current_user.id)


@router.delete(
    "/api-keys/{key_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="吊销API Key",
    description="吊销指定的API Key（软删除）",
)
async def revoke_api_key(
    key_id: int,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse:
    """吊销API Key"""
    service = AuthService(db)
    await service.revoke_api_key(current_user.id, key_id)
    return SuccessResponse(message="API Key已吊销")


# ============================================================
# 当前用户信息
# ============================================================

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
    description="返回当前登录用户的完整信息",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """获取当前用户信息"""
    return UserResponse.model_validate({
        **current_user.__dict__,
        "quota_remaining": current_user.quota_remaining,
    })
