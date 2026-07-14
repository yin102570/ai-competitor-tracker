"""
admin 模块单元测试
覆盖: 系统配置、备份、健康检查、权限控制
"""

import pytest


@pytest.mark.unit
class TestAdminSystemConfig:
    """系统配置测试"""

    @pytest.mark.asyncio
    async def test_get_config_admin(self, client, auth_headers):
        """admin可获取系统配置"""
        response = await client.get("/api/v1/admin/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "app_name" in data
        assert "app_version" in data
        assert "environment" in data
        assert "database_url_masked" in data
        assert "redis_url_masked" in data
        assert "deepseek_api_configured" in data
        assert "cors_origins" in data
        assert "max_quota_per_day" in data
        # 验证脱敏
        assert "***" in data["database_url_masked"] or "sqlite" in data["database_url_masked"]

    @pytest.mark.asyncio
    async def test_update_config_admin(self, client, auth_headers):
        """admin可更新系统配置"""
        response = await client.put(
            "/api/v1/admin/config",
            headers=auth_headers,
            json={"max_quota_per_day": 50, "default_page_size": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["max_quota_per_day"] == 50
        assert data["default_page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_config_non_admin(self, client, db_session):
        """非admin获取配置被拒"""
        from app.core.security import hash_password
        from app.models.user import User, UserRole

        user = User(
            email="viewer2@example.com",
            password_hash=hash_password("Viewer123!"),
            name="Viewer",
            role=UserRole.VIEWER.value,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "viewer2@example.com", "password": "Viewer123!"},
        )
        token = resp.json()["access_token"]

        response = await client.get(
            "/api/v1/admin/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


@pytest.mark.unit
class TestAdminBackup:
    """数据备份测试"""

    @pytest.mark.asyncio
    async def test_backup_admin(self, client, auth_headers):
        """admin可触发备份"""
        response = await client.post("/api/v1/admin/backup", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "backup_id" in data
        assert "tables_backed_up" in data
        assert len(data["tables_backed_up"]) > 0

    @pytest.mark.asyncio
    async def test_backup_non_admin(self, client, db_session):
        """非admin触发备份被拒"""
        from app.core.security import hash_password
        from app.models.user import User, UserRole

        user = User(
            email="analyst2@example.com",
            password_hash=hash_password("Analyst123!"),
            name="Analyst",
            role=UserRole.ANALYST.value,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "analyst2@example.com", "password": "Analyst123!"},
        )
        token = resp.json()["access_token"]

        response = await client.post(
            "/api/v1/admin/backup",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


@pytest.mark.unit
class TestAdminHealth:
    """健康检查测试（公开访问）"""

    @pytest.mark.asyncio
    async def test_health_public(self, client):
        """健康检查无需认证"""
        response = await client.get("/api/v1/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "version" in data
        assert "components" in data

        # 验证组件列表
        components = data["components"]
        names = [c["name"] for c in components]
        assert "database" in names
        assert "redis" in names
        assert "deepseek_api" in names

        # 数据库应该正常（测试环境）
        db_component = next(c for c in components if c["name"] == "database")
        assert db_component["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_with_auth(self, client, auth_headers):
        """认证用户也可访问健康检查"""
        response = await client.get("/api/v1/admin/health", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
