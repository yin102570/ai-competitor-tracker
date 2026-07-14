"""
users 模块单元测试
覆盖: 注册、更新、配额查询、角色管理、权限校验
"""

import pytest


@pytest.mark.unit
class TestUserRegister:
    """用户注册测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """正常注册应成功"""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "newuser@example.com",
                "password": "TestPass123!",
                "name": "新用户",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "新*"  # 脱敏
        assert data["role"] == "viewer"
        assert data["daily_quota"] == 5
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, test_user):
        """重复邮箱应返回409"""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "test@example.com",
                "password": "TestPass123!",
                "name": "重复用户",
            },
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONFLICT_DUPLICATE"

    @pytest.mark.asyncio
    async def test_register_weak_password_no_upper(self, client):
        """密码无大写应返回422"""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "weak@example.com",
                "password": "testpass123!",
                "name": "弱密码",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self, client):
        """密码无数字应返回422"""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "weak@example.com",
                "password": "TestPassword!",
                "name": "弱密码",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """非法邮箱应返回422"""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "not-an-email",
                "password": "TestPass123!",
                "name": "测试",
            },
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestUserUpdate:
    """用户更新测试"""

    @pytest.mark.asyncio
    async def test_update_me(self, client, auth_headers):
        """更新当前用户名称"""
        response = await client.put(
            "/api/v1/users/me",
            json={"name": "更新后的名字"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的名字"

    @pytest.mark.asyncio
    async def test_update_me_unauthorized(self, client):
        """未认证更新应返回401"""
        response = await client.put(
            "/api/v1/users/me",
            json={"name": "未授权"},
        )
        assert response.status_code == 401


@pytest.mark.unit
class TestUserQuota:
    """配额查询测试"""

    @pytest.mark.asyncio
    async def test_get_my_quota(self, client, auth_headers, test_user):
        """查询自己的配额"""
        response = await client.get(
            f"/api/v1/users/{test_user.id}/quota",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == test_user.id
        assert data["daily_quota"] == 100
        assert data["quota_remaining"] == 100

    @pytest.mark.asyncio
    async def test_get_other_user_quota_forbidden(self, client, auth_headers):
        """普通用户查询他人配额应返回403"""
        response = await client.get(
            "/api/v1/users/999/quota",
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "AUTH_PERMISSION_DENIED"


@pytest.mark.unit
class TestUserRole:
    """角色管理测试"""

    @pytest.mark.asyncio
    async def test_admin_update_role(self, client, auth_headers, test_user):
        """admin修改其他用户角色"""
        # 先创建一个新用户
        from app.core.security import hash_password
        from app.db.session import engine, async_session_factory
        from app.db.base import Base
        from app.models.user import User

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as session:
            new_user = User(
                email="target@example.com",
                password_hash=hash_password("TestPass123!"),
                name="目标用户",
                role="viewer",
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            target_id = new_user.id

        response = await client.put(
            f"/api/v1/users/{target_id}/role",
            json={"role": "analyst"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "analyst"

    @pytest.mark.asyncio
    async def test_admin_cannot_change_own_role(self, client, auth_headers, test_user):
        """admin不能修改自己的角色"""
        response = await client.put(
            f"/api/v1/users/{test_user.id}/role",
            json={"role": "viewer"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_update_role_forbidden(self, client, db_session):
        """非admin修改角色应返回403"""
        from app.core.security import hash_password
        from app.models.user import User

        # 创建一个viewer用户
        viewer = User(
            email="viewer@example.com",
            password_hash=hash_password("TestPass123!"),
            name="普通用户",
            role="viewer",
        )
        db_session.add(viewer)
        await db_session.commit()
        await db_session.refresh(viewer)

        # 登录获取token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "viewer@example.com", "password": "TestPass123!"},
        )
        viewer_token = login_resp.json()["access_token"]

        response = await client.put(
            f"/api/v1/users/{viewer.id}/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "AUTH_PERMISSION_DENIED"


@pytest.mark.unit
class TestUserList:
    """用户列表测试"""

    @pytest.mark.asyncio
    async def test_admin_list_users(self, client, auth_headers):
        """admin可查看用户列表"""
        response = await client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    @pytest.mark.asyncio
    async def test_non_admin_list_users_forbidden(self, client, db_session):
        """非admin查看列表应返回403"""
        from app.core.security import hash_password
        from app.models.user import User

        viewer = User(
            email="viewer2@example.com",
            password_hash=hash_password("TestPass123!"),
            name="普通用户",
            role="viewer",
        )
        db_session.add(viewer)
        await db_session.commit()

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "viewer2@example.com", "password": "TestPass123!"},
        )
        viewer_token = login_resp.json()["access_token"]

        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403
