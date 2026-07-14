"""
auth 模块单元测试
覆盖: 登录、令牌刷新、登出、API Key CRUD、权限校验
"""

import pytest


@pytest.mark.unit
class TestLogin:
    """登录接口测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """正确邮箱密码应登录成功"""
        # 先注册
        from app.core.security import hash_password
        from app.db.session import get_db
        from app.models.user import User, UserRole
        from app.db.base import Base
        from app.db.session import async_session_factory, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as session:
            user = User(
                email="logintest@example.com",
                password_hash=hash_password("TestPassword123!"),
                name="登录测试",
                role=UserRole.VIEWER.value,
            )
            session.add(user)
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "logintest@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """错误密码应返回401"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "WrongPassword123!"},
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """不存在用户应返回401（不暴露用户是否存在）"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, client):
        """非法邮箱格式应返回422"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "TestPassword123!"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_short_password(self, client):
        """密码过短应返回422"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "short"},
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestAuthEndpoints:
    """认证端点测试"""

    @pytest.mark.asyncio
    async def test_get_me(self, client, auth_headers):
        """已认证用户可获取自身信息"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "admin"
        assert "quota_remaining" in data

    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client):
        """未认证请求应返回401"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_token(self, client):
        """无效令牌应返回401"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code == 401


@pytest.mark.unit
class TestAPIKey:
    """API Key 管理测试"""

    @pytest.mark.asyncio
    async def test_create_api_key(self, client, auth_headers):
        """创建API Key应返回明文"""
        response = await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "测试Key"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "api_key" in data
        assert data["api_key"].startswith("act_")
        assert data["name"] == "测试Key"
        assert "warning" in data

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client, auth_headers):
        """列出API Key不含明文"""
        # 先创建一个
        await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "测试Key"},
            headers=auth_headers,
        )
        # 列出
        response = await client.get("/api/v1/auth/api-keys", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "api_key" not in data[0]  # 不含明文
        assert "key_prefix" in data[0]

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client, auth_headers):
        """吊销API Key后应不可用"""
        # 创建
        create_resp = await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "待吊销Key"},
            headers=auth_headers,
        )
        key_id = create_resp.json()["id"]

        # 吊销
        revoke_resp = await client.delete(
            f"/api/v1/auth/api-keys/{key_id}",
            headers=auth_headers,
        )
        assert revoke_resp.status_code == 200

        # 列表确认已吊销
        list_resp = await client.get("/api/v1/auth/api-keys", headers=auth_headers)
        keys = {k["id"]: k for k in list_resp.json()}
        assert keys[key_id]["is_active"] is False

    @pytest.mark.asyncio
    async def test_create_api_key_with_expiry(self, client, auth_headers):
        """创建带过期的API Key"""
        response = await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "临时Key", "expires_in_days": 30},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None


@pytest.mark.unit
class TestSecurityFunctions:
    """安全函数单元测试"""

    def test_hash_and_verify_password(self):
        """密码哈希与验证"""
        from app.core.security import hash_password, verify_password

        plain = "MySecurePassword123!"
        hashed = hash_password(plain)

        assert hashed != plain
        assert verify_password(plain, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_generate_api_key_format(self):
        """API Key生成格式"""
        from app.core.security import generate_api_key

        plaintext, key_hash, prefix = generate_api_key()

        assert plaintext.startswith("act_")
        assert len(plaintext) > 32
        assert len(key_hash) == 64  # SHA-256 hex
        assert prefix == plaintext[:8]

    def test_jwt_token_creation_and_decode(self):
        """JWT令牌创建与解码"""
        from app.core.security import create_access_token, decode_token

        token, jti = create_access_token(42, "admin")
        payload = decode_token(token)

        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert payload["jti"] == jti

    def test_token_response_format(self):
        """错误响应格式符合设计文档规范"""
        from app.core.exceptions import AuthError

        exc = AuthError.invalid_credentials()
        resp = exc.to_response("req_test123")

        assert resp["error_code"] == "AUTH_INVALID_CREDENTIALS"
        assert resp["message"] == "用户名或密码错误"
        assert resp["request_id"] == "req_test123"
        assert "timestamp" in resp
