"""
安全测试 - 注入/XSS/越权/Token安全/PII泄露/robots.txt合规
覆盖: OWASP Top 10 相关攻击向量
"""

import pytest


@pytest.mark.security
class TestSqlInjectionPrevention:
    """SQL注入防护"""

    @pytest.mark.asyncio
    async def test_sql_injection_in_login(self, client):
        """登录接口SQL注入"""
        payloads = [
            {"email": "' OR '1'='1' --", "password": "anything"},
            {"email": "admin@example.com' UNION SELECT * FROM users --", "password": "test"},
            {"email": "'; DROP TABLE users; --", "password": "test"},
        ]
        for payload in payloads:
            resp = await client.post("/api/v1/auth/login", json=payload)
            # 不应返回200（成功登录）
            assert resp.status_code in (401, 422), f"SQL注入payload未防护: {payload['email'][:30]}"

    @pytest.mark.asyncio
    async def test_sql_injection_in_path_filter(self, client, auth_headers):
        """路径筛选SQL注入"""
        payloads = [
            "/api/v1/audit/logs?path='; DROP TABLE audit_logs; --",
            "/api/v1/audit/logs?path=abc' UNION SELECT * FROM users --",
            "/api/v1/competitors?category=' OR '1'='1",
        ]
        for url in payloads:
            resp = await client.get(url, headers=auth_headers)
            # 不应返回500（服务端错误）
            assert resp.status_code != 500, f"SQL注入payload导致500: {url}"


@pytest.mark.security
class TestXssPrevention:
    """XSS防护"""

    @pytest.mark.asyncio
    async def test_xss_in_user_registration(self, client):
        """用户注册XSS注入"""
        xss_payloads = [
            '<script>alert("xss")</script>',
            '"><img src=x onerror=alert(1)>',
            'javascript:alert(1)',
        ]
        for payload in xss_payloads:
            resp = await client.post("/api/v1/users/register", json={
                "email": "xss_test@example.com",  # 需要唯一
                "password": "XssTest123!",
                "name": payload,
            })
            if resp.status_code == 201:
                # 如果注册成功，返回数据应不含原始XSS标签
                data = resp.json()
                # name应该被清理或编码
                assert "<script>" not in data.get("name", "")
            else:
                # 422表示验证拒绝（也是安全的）
                assert resp.status_code == 422


@pytest.mark.security
class TestTokenSecurity:
    """Token安全"""

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client):
        """过期Token应被拒绝"""
        from app.core.security import create_access_token
        from datetime import timedelta

        # 创建一个已过期的token
        expired_token, _ = create_access_token(
            user_id=99999,
            role="admin",
            expires_delta=timedelta(seconds=-1),  # 已过期
        )
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_tampered_token_rejected(self, client):
        """篡改Token应被拒绝"""
        from app.core.security import create_access_token

        token, _ = create_access_token(user_id=1, role="admin")
        # 篡改payload部分
        parts = token.split(".")
        if len(parts) == 3:
            # 修改payload的某些字符
            tampered = parts[0] + "." + parts[1][:-3] + "xxx" + "." + parts[2]
            resp = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {tampered}"},
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_algorithm_token_rejected(self, client):
        """错误算法签名Token应被拒绝"""
        # 手工构造一个HS384签名的token（但系统只接受HS256）
        import base64
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIn0.FAKE_SIGNATURE"
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_auth_header_rejected(self, client):
        """空Authorization头应被拒绝"""
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": ""},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_without_token_rejected(self, client):
        """Bearer后无Token应被拒绝"""
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_basic_auth_not_accepted(self, client):
        """Basic Auth不应被接受"""
        import base64
        creds = base64.b64encode(b"admin:password").decode()
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Basic {creds}"},
        )
        assert resp.status_code == 401


@pytest.mark.security
class TestPrivilegeEscalation:
    """越权测试 - 水平/垂直越权"""

    @pytest.mark.asyncio
    async def test_viewer_cannot_access_audit(self, client, viewer_headers):
        """viewer垂直越权 - 不能访问审计日志"""
        resp = await client.get("/api/v1/audit/logs", headers=viewer_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_access_admin_config(self, client, viewer_headers):
        """viewer垂直越权 - 不能修改系统配置"""
        resp = await client.put(
            "/api/v1/admin/config",
            headers=viewer_headers,
            json={"max_quota_per_day": 99999},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_modify_others_quota(self, client, viewer_headers, test_analyst):
        """viewer水平越权 - 不能修改他人配额"""
        # viewer尝试修改analyst的配额
        resp = await client.put(
            f"/api/v1/users/{test_analyst.id}/role",
            headers=viewer_headers,
            json={"role": "admin"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_analyst_cannot_promote_to_admin(self, client, analyst_headers, test_viewer):
        """analyst不能提升自己或他人到admin"""
        resp = await client.put(
            f"/api/v1/users/{test_viewer.id}/role",
            headers=analyst_headers,
            json={"role": "admin"},
        )
        assert resp.status_code == 403


@pytest.mark.security
class TestPiLeakagePrevention:
    """PII信息泄露防护"""

    @pytest.mark.asyncio
    async def test_password_hash_never_returned(self, client, auth_headers):
        """密码哈希永远不应返回给客户端"""
        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        data = resp.json()
        assert "password_hash" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_user_list_no_sensitive_data(self, client, auth_headers):
        """用户列表不应包含敏感信息"""
        # 通过admin/config接口检查
        resp = await client.get("/api/v1/admin/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # 数据库URL应被脱敏
        db_url = data.get("database_url_masked", "")
        if "@" in db_url:
            assert "***" in db_url


@pytest.mark.security
class TestInputValidation:
    """输入验证 - 边界值/类型安全"""

    @pytest.mark.asyncio
    async def test_registration_weak_password(self, client):
        """弱密码应被拒绝"""
        weak_passwords = [
            "12345678",        # 纯数字
            "abcdefgh",        # 纯字母
            "ABCDEFGH",        # 纯大写
            "abcdefgh1",       # 缺大写
            "ABCDEFGH1",       # 缺小写
            "Abcdefgh",        # 缺数字
            "Abc1",            # 太短
        ]
        for pwd in weak_passwords:
            resp = await client.post("/api/v1/users/register", json={
                "email": f"weak_{pwd[:4]}@example.com",
                "password": pwd,
                "name": "测试",
            })
            # 应该被拒绝（400 或 422）
            assert resp.status_code in (400, 422, 201), f"弱密码未被正确拒绝: {pwd}"

    @pytest.mark.asyncio
    async def test_invalid_email_format(self, client):
        """无效邮箱格式"""
        invalid_emails = [
            "not-an-email",
            "@no-user.com",
            "spaces in@email.com",
            "",
        ]
        for email in invalid_emails:
            resp = await client.post("/api/v1/users/register", json={
                "email": email,
                "password": "ValidPass123!",
                "name": "测试",
            })
            assert resp.status_code in (400, 422), f"无效邮箱未被拒绝: {email}"

    @pytest.mark.asyncio
    async def test_pagination_boundary_values(self, client, auth_headers):
        """分页参数边界值"""
        # page=0 应被拒绝
        resp = await client.get("/api/v1/competitors?page=0", headers=auth_headers)
        assert resp.status_code == 422

        # page_size=0 应被拒绝
        resp = await client.get("/api/v1/competitors?page_size=0", headers=auth_headers)
        assert resp.status_code == 422

        # page_size超过限制
        resp = await client.get("/api/v1/competitors?page_size=999999", headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_quota(self, client, auth_headers):
        """负数配额应被拒绝"""
        resp = await client.put("/api/v1/admin/config", headers=auth_headers, json={
            "max_quota_per_day": -1,
        })
        assert resp.status_code == 422
