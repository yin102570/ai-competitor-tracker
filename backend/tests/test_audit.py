"""
audit 模块单元测试
覆盖: 审计日志查询、统计、权限控制
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.audit import AuditLog


@pytest.fixture
async def sample_audit_logs(db_session):
    """预置审计日志测试数据"""
    logs = [
        AuditLog(
            request_id="req_001",
            user_id=1,
            user_email="admin@example.com",
            method="GET",
            path="/api/v1/competitors",
            status_code=200,
            client_ip="127.0.0.1",
            cost_tokens=1,
            response_time_ms=45,
        ),
        AuditLog(
            request_id="req_002",
            user_id=1,
            user_email="admin@example.com",
            method="POST",
            path="/api/v1/competitors",
            status_code=201,
            client_ip="127.0.0.1",
            cost_tokens=2,
            response_time_ms=120,
        ),
        AuditLog(
            request_id="req_003",
            user_id=None,
            user_email=None,
            method="GET",
            path="/api/v1/auth/login",
            status_code=401,
            client_ip="192.168.1.1",
            cost_tokens=0,
            response_time_ms=15,
            error_code="AUTH_INVALID_CREDENTIALS",
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()


@pytest.mark.unit
class TestAuditLogs:
    """审计日志查询测试"""

    @pytest.mark.asyncio
    async def test_list_logs_admin(self, client, auth_headers, sample_audit_logs):
        """admin可查看审计日志"""
        response = await client.get("/api/v1/audit/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3

    @pytest.mark.asyncio
    async def test_list_logs_filter_by_method(self, client, auth_headers, sample_audit_logs):
        """按HTTP方法筛选"""
        response = await client.get(
            "/api/v1/audit/logs?method=GET", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["method"] == "GET"

    @pytest.mark.asyncio
    async def test_list_logs_filter_by_status(self, client, auth_headers, sample_audit_logs):
        """按状态码筛选"""
        response = await client.get(
            "/api/v1/audit/logs?status_code=401", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status_code"] == 401

    @pytest.mark.asyncio
    async def test_list_logs_pagination(self, client, auth_headers, sample_audit_logs):
        """分页功能"""
        response = await client.get(
            "/api/v1/audit/logs?page=1&page_size=2", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_list_logs_filter_by_path(self, client, auth_headers, sample_audit_logs):
        """按路径模糊匹配筛选"""
        response = await client.get(
            "/api/v1/audit/logs?path=competitors", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert "competitors" in item["path"]


@pytest.mark.unit
class TestAuditStats:
    """审计统计测试"""

    @pytest.mark.asyncio
    async def test_stats_admin(self, client, auth_headers, sample_audit_logs):
        """admin可查看统计"""
        response = await client.get("/api/v1/audit/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "total_cost" in data
        assert "avg_response_time_ms" in data
        assert "error_rate_pct" in data
        assert "top_paths" in data
        assert "top_users" in data
        assert data["time_range"] == "7d"

    @pytest.mark.asyncio
    async def test_stats_custom_days(self, client, auth_headers, sample_audit_logs):
        """自定义统计天数"""
        response = await client.get(
            "/api/v1/audit/stats?days=1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "1d"

    @pytest.mark.asyncio
    async def test_stats_empty(self, client, auth_headers):
        """无数据时统计返回零值"""
        response = await client.get("/api/v1/audit/stats?days=1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 0
        assert data["total_cost"] == 0
        assert data["avg_response_time_ms"] == 0.0
        assert data["error_rate_pct"] == 0.0


@pytest.mark.unit
class TestAuditPermission:
    """权限控制测试"""

    @pytest.mark.asyncio
    async def test_list_logs_non_admin(self, client, db_session):
        """非admin用户访问被拒"""
        from app.core.security import hash_password
        from app.models.user import User, UserRole

        # 创建viewer用户
        user = User(
            email="viewer@example.com",
            password_hash=hash_password("Viewer123!"),
            name="Viewer",
            role=UserRole.VIEWER.value,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # 登录获取token
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "viewer@example.com", "password": "Viewer123!"},
        )
        token = resp.json()["access_token"]

        # 访问audit接口
        response = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_stats_non_admin(self, client, db_session):
        """非admin用户访问统计被拒"""
        from app.core.security import hash_password
        from app.models.user import User, UserRole

        user = User(
            email="analyst@example.com",
            password_hash=hash_password("Analyst123!"),
            name="Analyst",
            role=UserRole.ANALYST.value,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@example.com", "password": "Analyst123!"},
        )
        token = resp.json()["access_token"]

        response = await client.get(
            "/api/v1/audit/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_logs_no_auth(self, client):
        """未认证访问被拒"""
        response = await client.get("/api/v1/audit/logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stats_no_auth(self, client):
        """未认证访问统计被拒"""
        response = await client.get("/api/v1/audit/stats")
        assert response.status_code == 401
