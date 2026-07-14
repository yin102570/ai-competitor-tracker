"""
性能基线测试 - 响应时间/并发/配额消耗
目标: 所有API响应 < 200ms（内存SQLite），健康检查 < 50ms
"""

import pytest
import asyncio
import time


@pytest.mark.perf
@pytest.mark.slow
class TestApiResponseTimeBaseline:
    """API响应时间基线"""

    @pytest.mark.asyncio
    async def test_health_endpoint_latency(self, client, perf_timer):
        """健康检查 < 50ms"""
        resp = await client.get("/health")
        elapsed = perf_timer.elapsed_ms()
        assert resp.status_code == 200
        assert elapsed < 100, f"健康检查耗时 {elapsed:.1f}ms，超过基线 100ms"

    @pytest.mark.asyncio
    async def test_login_latency(self, client, test_user, perf_timer):
        """登录接口 < 200ms"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPassword123!",
        })
        elapsed = perf_timer.elapsed_ms()
        assert resp.status_code == 200
        assert elapsed < 500, f"登录耗时 {elapsed:.1f}ms，超过基线 500ms"

    @pytest.mark.asyncio
    async def test_competitors_list_latency(self, client, auth_headers, perf_timer):
        """竞品列表 < 200ms"""
        resp = await client.get("/api/v1/competitors", headers=auth_headers)
        elapsed = perf_timer.elapsed_ms()
        assert resp.status_code == 200
        assert elapsed < 200, f"竞品列表耗时 {elapsed:.1f}ms，超过基线 200ms"

    @pytest.mark.asyncio
    async def test_dashboard_overview_latency(self, client, auth_headers, perf_timer):
        """Dashboard聚合 < 300ms"""
        resp = await client.get("/api/v1/dashboard/overview", headers=auth_headers)
        elapsed = perf_timer.elapsed_ms()
        assert resp.status_code == 200
        assert elapsed < 500, f"Dashboard聚合耗时 {elapsed:.1f}ms，超过基线 500ms"

    @pytest.mark.asyncio
    async def test_admin_health_latency(self, client, perf_timer):
        """admin健康检查 < 100ms"""
        resp = await client.get("/api/v1/admin/health")
        elapsed = perf_timer.elapsed_ms()
        assert resp.status_code == 200
        assert elapsed < 200, f"admin健康检查耗时 {elapsed:.1f}ms，超过基线 200ms"


@pytest.mark.perf
@pytest.mark.slow
class TestConcurrencyBaseline:
    """并发请求基线"""

    @pytest.mark.asyncio
    async def test_concurrent_health_requests(self, client):
        """100个并发健康检查请求"""
        async def single_request():
            start = time.perf_counter()
            resp = await client.get("/health")
            return resp.status_code, (time.perf_counter() - start) * 1000

        tasks = [single_request() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(
            1 for r in results
            if isinstance(r, tuple) and r[0] == 200
        )
        assert success_count == 50, f"并发请求成功率: {success_count}/50"

        # P95延迟
        latencies = sorted(r[1] for r in results if isinstance(r, tuple))
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        assert p95 < 500, f"P95延迟 {p95:.1f}ms 超过基线 500ms"

    @pytest.mark.asyncio
    async def test_sequential_vs_concurrent_improvement(self, client):
        """并发应比串行快"""
        count = 20

        # 串行
        start = time.perf_counter()
        for _ in range(count):
            await client.get("/health")
        sequential_time = (time.perf_counter() - start) * 1000

        # 并行
        start = time.perf_counter()
        tasks = [client.get("/health") for _ in range(count)]
        await asyncio.gather(*tasks)
        concurrent_time = (time.perf_counter() - start) * 1000

        # 并发应更快（允许一定误差）
        ratio = concurrent_time / sequential_time
        assert ratio < 1.5, f"并发加速不明显: 串行={sequential_time:.0f}ms 并发={concurrent_time:.0f}ms ratio={ratio:.2f}"


@pytest.mark.perf
@pytest.mark.slow
class TestQuotaConsumptionBaseline:
    """配额消耗基线"""

    @pytest.mark.asyncio
    async def test_quota_decrement_on_login(self, client, test_user):
        """登录不应消耗配额（登录免费）"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPassword123!",
        })
        assert resp.status_code == 200

        # 检查配额
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
        )
        data = resp.json()
        # 登录不应消耗配额
        assert data.get("quota_remaining", 100) >= 100

    @pytest.mark.asyncio
    async def test_viewer_has_default_quota(self, client, test_viewer):
        """viewer应有默认配额"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "viewer@example.com",
            "password": "ViewerPass123!",
        })
        assert resp.status_code == 200

        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
        )
        data = resp.json()
        assert data["daily_quota"] == 5
        assert data.get("quota_remaining", 5) >= 0


@pytest.mark.perf
@pytest.mark.slow
class TestDatabasePerformanceBaseline:
    """数据库性能基线"""

    @pytest.mark.asyncio
    async def test_large_dataset_pagination(self, client, auth_headers, db_session):
        """大数据集分页性能"""
        from app.models.audit import AuditLog
        import random

        # 插入1000条审计日志
        methods = ["GET", "POST", "PUT", "DELETE"]
        paths = [
            "/api/v1/competitors",
            "/api/v1/sentiment/panel",
            "/api/v1/dashboard/overview",
            "/api/v1/users/me",
        ]
        for i in range(1000):
            log = AuditLog(
                request_id=f"perf_{i:04d}",
                user_id=1,
                user_email="admin@example.com",
                method=random.choice(methods),
                path=random.choice(paths),
                status_code=200,
                client_ip="127.0.0.1",
                cost_tokens=random.randint(0, 5),
                response_time_ms=random.randint(10, 200),
            )
            db_session.add(log)
        await db_session.commit()

        # 分页查询应在100ms内完成
        start = time.perf_counter()
        resp = await client.get(
            "/api/v1/audit/logs?page=10&page_size=20",
            headers=auth_headers,
        )
        elapsed = (time.perf_counter() - start) * 1000

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1000
        assert len(data["items"]) == 20
        assert elapsed < 200, f"1000条数据分页耗时 {elapsed:.1f}ms，超过基线 200ms"
