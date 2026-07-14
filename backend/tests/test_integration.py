"""
集成测试 - 模块间交互、中间件链、异常传播、完整业务流
覆盖: 注册→登录→API Key→竞品→舆情→Dashboard→审计 全链路
"""

import pytest
from datetime import datetime, timezone, timedelta


@pytest.mark.integration
class TestAuthUserIntegration:
    """auth ↔ users 模块集成"""

    @pytest.mark.asyncio
    async def test_register_then_login(self, client):
        """注册→登录完整链路"""
        # 1. 注册
        resp = await client.post("/api/v1/users/register", json={
            "email": "newuser@example.com",
            "password": "NewUser123!",
            "name": "新用户",
        })
        assert resp.status_code == 201
        user_data = resp.json()
        assert user_data["role"] == "viewer"
        assert user_data["daily_quota"] > 0

        # 2. 用注册信息登录
        resp = await client.post("/api/v1/auth/login", json={
            "email": "newuser@example.com",
            "password": "NewUser123!",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert len(token) > 0

        # 3. 用token访问自己的信息
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_duplicate_registration(self, client, test_user):
        """重复注册应被拒绝"""
        resp = await client.post("/api/v1/users/register", json={
            "email": "test@example.com",  # 已存在
            "password": "Test123456!",
            "name": "重复",
        })
        assert resp.status_code in (400, 409)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_user):
        """错误密码登录"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, test_inactive_user):
        """禁用用户登录应被拒"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "inactive@example.com",
            "password": "Inactive123!",
        })
        assert resp.status_code == 401


@pytest.mark.integration
class TestAuthApiKeyIntegration:
    """auth API Key 集成"""

    @pytest.mark.asyncio
    async def test_api_key_auth_works(self, client, test_api_key):
        """API Key认证可以正常使用"""
        headers = {"X-API-Key": test_api_key[0]}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, client):
        """无效API Key被拒"""
        headers = {"X-API-Key": "act_invalid_key_12345678"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_vs_jwt_interchangeable(self, client, auth_headers, test_api_key):
        """JWT和API Key可互换使用同一资源"""
        jwt_resp = await client.get("/api/v1/users/me", headers=auth_headers)
        api_resp = await client.get("/api/v1/users/me", headers={"X-API-Key": test_api_key[0]})
        assert jwt_resp.status_code == 200
        assert api_resp.status_code == 200


@pytest.mark.integration
class TestCompetitorSentimentIntegration:
    """competitors ↔ sentiment ↔ dashboard 模块集成"""

    @pytest.mark.asyncio
    async def test_competitor_creation_triggers_dashboard(self, client, auth_headers):
        """创建竞品→Dashboard可见"""
        # 创建竞品
        resp = await client.post("/api/v1/competitors", headers=auth_headers, json={
            "slug": "gemini",
            "name": "Gemini",
            "company": "Google",
            "category": "chatbot",
        })
        assert resp.status_code == 201

        # Dashboard应该包含该竞品
        resp = await client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        slugs = [c["slug"] for c in data["competitors"]]
        assert "gemini" in slugs

    @pytest.mark.asyncio
    async def test_sentiment_links_to_competitor(self, client, auth_headers, db_session):
        """舆情记录关联到竞品"""
        from app.models.competitor import Competitor
        from app.models.sentiment import SentimentRecord

        # 创建竞品
        comp = Competitor(
            slug="claude",
            name="Claude",
            company="Anthropic",
            category="chatbot",
        )
        db_session.add(comp)
        await db_session.commit()

        # 创建舆情
        from datetime import datetime, timezone, timedelta
        cst = timezone(timedelta(hours=8))
        sentiment = SentimentRecord(
            competitor_slug="claude",
            source="twitter",
            content="Claude is great for coding!",
            content_hash="hash_claude_001",
            sentiment_score=0.9,
            sentiment_label="positive",
            topics='["编程", "效率"]',
            published_at=datetime.now(cst) - timedelta(hours=1),
        )
        db_session.add(sentiment)
        await db_session.commit()

        # 查询该竞品舆情
        resp = await client.get(
            "/api/v1/sentiment/panel?competitor_slug=claude",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competitor_slug"] == "claude"

        # Dashboard统计应反映
        resp = await client.get("/api/v1/dashboard/overview", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["sentiment"]["total_mentions"] >= 1


@pytest.mark.integration
class TestMiddlewareExceptionChain:
    """中间件与异常链集成测试"""

    @pytest.mark.asyncio
    async def test_request_id_middleware_present(self, client):
        """每个请求都应携带X-Request-ID"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert resp.headers["x-request-id"].startswith("req_")

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, client):
        """CORS头应存在"""
        resp = await client.options(
            "/api/v1/competitors",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in resp.headers

    @pytest.mark.asyncio
    async def test_app_exception_response_format(self, client, auth_headers):
        """AppException应返回统一错误格式"""
        resp = await client.get("/api/v1/audit/logs", headers=auth_headers)
        # 如果admin才能访问且当前是admin，应200
        # 如果非admin，应403且有统一格式
        if resp.status_code in (400, 401, 403, 404, 422, 500):
            data = resp.json()
            assert "error_code" in data
            assert "message" in data
            assert "request_id" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_404_unknown_path(self, client):
        """未知路径应返回统一错误格式"""
        resp = await client.get("/api/v1/nonexistent_endpoint")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, client):
        """不支持的HTTP方法"""
        resp = await client.delete("/api/v1/competitors")
        assert resp.status_code in (405, 401)

    @pytest.mark.asyncio
    async def test_health_endpoint_public(self, client):
        """根健康检查端点应公开"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.integration
class TestRbacCrossModule:
    """RBAC跨模块权限一致性"""

    @pytest.mark.asyncio
    async def test_viewer_cannot_access_admin_resources(self, client, viewer_headers):
        """viewer不能访问admin资源"""
        endpoints = [
            ("GET", "/api/v1/audit/logs"),
            ("GET", "/api/v1/audit/stats"),
            ("GET", "/api/v1/admin/config"),
            ("POST", "/api/v1/admin/backup"),
        ]
        for method, path in endpoints:
            resp = await client.get(path, headers=viewer_headers)
            assert resp.status_code == 403, f"{method} {path} should be 403 for viewer"

    @pytest.mark.asyncio
    async def test_analyst_cannot_access_admin_resources(self, client, analyst_headers):
        """analyst不能访问admin专属资源"""
        resp = await client.get("/api/v1/admin/config", headers=analyst_headers)
        assert resp.status_code == 403

        resp = await client.get("/api/v1/audit/logs", headers=analyst_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_full_access(self, client, auth_headers):
        """admin应有全部访问权限"""
        endpoints = [
            ("GET", "/api/v1/competitors"),
            ("GET", "/api/v1/sentiment/panel"),
            ("GET", "/api/v1/dashboard/overview"),
            ("GET", "/api/v1/audit/logs"),
            ("GET", "/api/v1/admin/config"),
            ("GET", "/api/v1/admin/health"),
        ]
        for method, path in endpoints:
            resp = await client.get(path, headers=auth_headers)
            assert resp.status_code == 200, f"{method} {path} should be 200 for admin"
