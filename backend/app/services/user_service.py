"""
Users业务逻辑层 - 用户注册、资料更新、配额查询、角色管理
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, BusinessError, NotFoundError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import UserResponse
from app.schemas.user import (
    UserListItem,
    UserQuotaResponse,
    UserRegisterRequest,
    UserRegisteredResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)


class UserService:
    """用户服务 - 所有方法均为async"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 用户注册
    # ============================================================

    async def register(self, request: UserRegisterRequest) -> UserRegisteredResponse:
        """
        用户注册
        流程: 检查邮箱唯一性 → 密码哈希 → 创建用户 → 返回脱敏信息
        默认角色: viewer，默认配额: 5次/日
        """
        # 检查邮箱是否已存在
        existing = await self.db.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise BusinessError.duplicate("email", request.email)

        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            name=request.name,
            role=UserRole.VIEWER.value,
            daily_quota=5,  # 新用户默认5次/日
            quota_used=0,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()

        return UserRegisteredResponse.model_validate({
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "daily_quota": user.daily_quota,
            "created_at": user.created_at,
        })

    # ============================================================
    # 更新当前用户
    # ============================================================

    async def update_me(self, user_id: int, request: UserUpdateRequest) -> UserResponse:
        """更新当前用户信息"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError.user(user_id)

        if request.name is not None:
            user.name = request.name

        await self.db.flush()
        return UserResponse.model_validate({
            **user.__dict__,
            "quota_remaining": user.quota_remaining,
        })

    # ============================================================
    # 配额查询
    # ============================================================

    async def get_quota(self, target_user_id: int, current_user: User) -> UserQuotaResponse:
        """
        查询用户配额
        权限: admin可查询任意用户，普通用户仅可查询自己
        """
        # 权限校验
        if current_user.id != target_user_id and not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        result = await self.db.execute(
            select(User).where(User.id == target_user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError.user(target_user_id)

        return UserQuotaResponse(
            user_id=user.id,
            email=user.email,
            daily_quota=user.daily_quota,
            quota_used=user.quota_used,
            quota_remaining=user.quota_remaining,
            quota_reset_at=user.quota_reset_at,
            is_active=user.is_active,
        )

    # ============================================================
    # 角色管理 (admin only)
    # ============================================================

    async def update_role(
        self,
        target_user_id: int,
        request: UserRoleUpdateRequest,
        current_user: User,
    ) -> UserResponse:
        """
        修改用户角色
        权限: 仅admin可操作
        """
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        # 不能修改自己的角色（防止admin自降权限导致系统锁定）
        if target_user_id == current_user.id:
            raise BusinessError.validation_failed(
                [{"field": "user_id", "message": "不能修改自己的角色"}]
            )

        result = await self.db.execute(
            select(User).where(User.id == target_user_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError.user(target_user_id)

        user.role = request.role
        await self.db.flush()

        return UserResponse.model_validate({
            **user.__dict__,
            "quota_remaining": user.quota_remaining,
        })

    # ============================================================
    # 用户列表 (admin only)
    # ============================================================

    async def list_users(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UserListItem], int]:
        """
        列出所有用户
        权限: 仅admin可查看完整用户列表
        """
        if not current_user.is_admin:
            raise AuthError.permission_denied("admin")

        # 查询总数
        count_result = await self.db.execute(select(User))
        total = len(count_result.scalars().all())

        # 分页查询
        result = await self.db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = result.scalars().all()

        return [UserListItem.model_validate(u) for u in users], total
