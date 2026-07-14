"""
Users模块API路由 - 用户注册、资料管理、配额查询、角色管理
路由前缀: /api/v1/users

接口清单:
  POST   /register             用户注册（公开）
  GET    /me                   获取当前用户信息（已在auth模块实现，此处复用）
  PUT    /me                   更新当前用户信息
  GET    /{user_id}/quota     查询用户配额（admin/本人）
  PUT    /{user_id}/role      修改用户角色（admin only）
  GET    /                     用户列表（admin only）
"""

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DBSession, PaginationDep, require_role
from app.models.user import UserRole
from app.schemas.auth import UserResponse
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.user import (
    UserQuotaResponse,
    UserRegisterRequest,
    UserRegisteredResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


# ============================================================
# 当前用户信息（必须在 /{user_id}/quota 之前定义，否则路由匹配冲突）
# ============================================================

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
    description="返回当前登录用户的完整信息",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """获取当前用户信息"""
    return UserResponse.model_validate({
        **current_user.__dict__,
        "quota_remaining": current_user.quota_remaining,
    })


# ============================================================
# 用户注册（公开接口）
# ============================================================

@router.post(
    "/register",
    response_model=UserRegisteredResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="新用户注册，默认分配5次/日免费配额，角色为viewer",
)
async def register(
    request: UserRegisterRequest,
    db: DBSession,
) -> UserRegisteredResponse:
    """用户注册"""
    service = UserService(db)
    return await service.register(request)


# ============================================================
# 当前用户资料管理
# ============================================================

@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="更新当前用户信息",
    description="更新当前登录用户的显示名称等资料",
)
async def update_me(
    request: UserUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> UserResponse:
    """更新当前用户信息"""
    service = UserService(db)
    return await service.update_me(current_user.id, request)


# ============================================================
# 配额查询
# ============================================================

@router.get(
    "/{user_id}/quota",
    response_model=UserQuotaResponse,
    status_code=status.HTTP_200_OK,
    summary="查询用户配额",
    description="查询指定用户的配额使用情况。admin可查询任意用户，普通用户仅可查询自己",
)
async def get_user_quota(
    user_id: int,
    db: DBSession,
    current_user: CurrentUser,
) -> UserQuotaResponse:
    """查询用户配额"""
    service = UserService(db)
    return await service.get_quota(user_id, current_user)


# ============================================================
# 角色管理 (admin only)
# ============================================================

@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="修改用户角色",
    description="修改指定用户的角色。仅admin可操作，且不能修改自己的角色",
)
async def update_user_role(
    user_id: int,
    request: UserRoleUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> UserResponse:
    """修改用户角色"""
    service = UserService(db)
    return await service.update_role(user_id, request, current_user)


# ============================================================
# 用户列表 (admin only)
# ============================================================

@router.get(
    "/",
    response_model=PaginatedResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="用户列表",
    description="获取所有用户列表。仅admin可访问",
)
async def list_users(
    db: DBSession,
    current_user: CurrentUser,
    pagination: PaginationDep,
) -> PaginatedResponse[UserResponse]:
    """用户列表（分页）"""
    service = UserService(db)
    users, total = await service.list_users(
        current_user,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse[UserResponse](
        items=[UserResponse.model_validate({
            **u.__dict__,
            "quota_remaining": u.daily_quota - u.quota_used,
        }) for u in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )
