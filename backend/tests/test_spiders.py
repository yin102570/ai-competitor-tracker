"""
spiders 模块单元测试
覆盖: 触发任务、查询状态、任务列表、取消任务、调度配置、权限校验
"""

import pytest


@pytest.fixture
async def sample_competitor(db_session):
    """预置测试竞品"""
    from app.models.competitor import Competitor

    comp = Competitor(
        slug="chatgpt",
        name="ChatGPT",
        company="OpenAI",
        category="chatbot",
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)
    return comp


@pytest.mark.unit
class TestSpiderTrigger:
    """触发爬虫任务测试"""

    @pytest.mark.asyncio
    async def test_trigger_web_task(self, client, auth_headers, sample_competitor):
        """触发Web流量采集任务"""
        response = await client.post(
            "/api/v1/spiders/trigger",
            json={
                "competitor_slug": "chatgpt",
                "task_type": "web",
                "priority": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"].startswith("task_")
        assert data["competitor_slug"] == "chatgpt"
        assert data["task_type"] == "web"
        assert data["status"] == "success"
        assert data["duration_seconds"] is not None
        assert data["result"] is not None

    @pytest.mark.asyncio
    async def test_trigger_sentiment_task(self, client, auth_headers, sample_competitor):
        """触发舆情采集任务"""
        response = await client.post(
            "/api/v1/spiders/trigger",
            json={
                "competitor_slug": "chatgpt",
                "task_type": "sentiment",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["task_type"] == "sentiment"

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_competitor(self, client, auth_headers):
        """不存在的竞品应返回404"""
        response = await client.post(
            "/api/v1/spiders/trigger",
            json={
                "competitor_slug": "nonexistent",
                "task_type": "web",
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND_COMPETITOR"

    @pytest.mark.asyncio
    async def test_trigger_invalid_task_type(self, client, auth_headers, sample_competitor):
        """非法任务类型应返回422"""
        response = await client.post(
            "/api/v1/spiders/trigger",
            json={
                "competitor_slug": "chatgpt",
                "task_type": "invalid_type",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestSpiderTaskQuery:
    """任务查询测试"""

    @pytest.mark.asyncio
    async def test_get_task(self, client, auth_headers, sample_competitor):
        """查询单个任务状态"""
        # 先触发
        trigger_resp = await client.post(
            "/api/v1/spiders/trigger",
            json={"competitor_slug": "chatgpt", "task_type": "app"},
            headers=auth_headers,
        )
        task_id = trigger_resp.json()["id"]

        # 查询
        response = await client.get(f"/api/v1/spiders/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["task_type"] == "app"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, client):
        """不存在的任务应返回404"""
        response = await client.get("/api/v1/spiders/tasks/task_nonexistent")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND_SPIDER_TASK"


@pytest.mark.unit
class TestSpiderTaskList:
    """任务列表测试"""

    @pytest.mark.asyncio
    async def test_list_tasks(self, client, auth_headers, sample_competitor):
        """获取任务列表"""
        # 先触发两个任务
        await client.post(
            "/api/v1/spiders/trigger",
            json={"competitor_slug": "chatgpt", "task_type": "web"},
            headers=auth_headers,
        )
        await client.post(
            "/api/v1/spiders/trigger",
            json={"competitor_slug": "chatgpt", "task_type": "pricing"},
            headers=auth_headers,
        )

        response = await client.get("/api/v1/spiders/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_list_by_type(self, client, auth_headers, sample_competitor):
        """按任务类型筛选"""
        await client.post(
            "/api/v1/spiders/trigger",
            json={"competitor_slug": "chatgpt", "task_type": "web"},
            headers=auth_headers,
        )

        response = await client.get(
            "/api/v1/spiders/tasks",
            params={"task_type": "web"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["task_type"] == "web"

    @pytest.mark.asyncio
    async def test_list_by_status(self, client, auth_headers, sample_competitor):
        """按状态筛选"""
        response = await client.get(
            "/api/v1/spiders/tasks",
            params={"status": "success"},
        )
        assert response.status_code == 200


@pytest.mark.unit
class TestSpiderSchedule:
    """调度配置测试"""

    @pytest.mark.asyncio
    async def test_get_schedule(self, client, auth_headers):
        """获取调度配置"""
        response = await client.get("/api/v1/spiders/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "schedule" in data
        assert len(data["schedule"]) == 5
        assert data["concurrency_limit"] == 5
        assert data["rate_limit_per_sec"] == 2

        # 验证调度规则
        task_types = [s["task_type"] for s in data["schedule"]]
        assert "web" in task_types
        assert "app" in task_types
        assert "sentiment" in task_types


@pytest.mark.unit
class TestSpiderCancel:
    """取消任务测试"""

    @pytest.mark.asyncio
    async def test_cancel_running_task_fails(self, client, auth_headers, sample_competitor):
        """已完成的任务不能取消"""
        # 触发后已完成
        trigger_resp = await client.post(
            "/api/v1/spiders/trigger",
            json={"competitor_slug": "chatgpt", "task_type": "web"},
            headers=auth_headers,
        )
        task_id = trigger_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/spiders/tasks/{task_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
