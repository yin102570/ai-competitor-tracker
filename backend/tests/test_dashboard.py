"""
dashboard 模块单元测试
覆盖: 综合看板聚合、WebSocket连接
"""

import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture
async def sample_dashboard_data(db_session):
    """预置Dashboard测试数据"""
    from app.models.competitor import Competitor, CompetitorHistory
    from app.models.sentiment import SentimentRecord
    from app.models.spider import SpiderTask, TaskStatus

    cst = timezone(timedelta(hours=8))

    # 创建竞品
    comp = Competitor(
        slug="chatgpt",
        name="ChatGPT",
        company="OpenAI",
        category="chatbot",
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    # 创建历史快照
    history = CompetitorHistory(
        competitor_slug="chatgpt",
        date=datetime.now(cst).date(),
        monthly_visits=1_800_000_000,
        ios_downloads=45_000_000,
        arena_score=1289,
        arena_rank=3,
    )
    db_session.add(history)

    # 创建舆情记录
    sentiment = SentimentRecord(
        competitor_slug="chatgpt",
        source="twitter",
        content="ChatGPT is amazing!",
        content_hash="hash1",
        sentiment_score=0.85,
        sentiment_label="positive",
        topics='["功能", "用户体验"]',
        published_at=datetime.now(cst) - timedelta(hours=1),
    )
    db_session.add(sentiment)

    # 创建爬虫任务
    task = SpiderTask(
        id="task_test123",
        competitor_slug="chatgpt",
        task_type="web",
        status=TaskStatus.SUCCESS.value,
        started_at=datetime.now(cst) - timedelta(hours=2),
        completed_at=datetime.now(cst) - timedelta(hours=1),
    )
    db_session.add(task)
    await db_session.commit()


@pytest.mark.unit
class TestDashboardOverview:
    """综合看板测试"""

    @pytest.mark.asyncio
    async def test_dashboard_overview(self, client, sample_dashboard_data):
        """获取综合看板"""
        response = await client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()

        # 验证结构
        assert "competitors" in data
        assert "sentiment" in data
        assert "spiders" in data
        assert "system" in data
        assert "updated_at" in data

        # 验证竞品数据
        assert len(data["competitors"]) >= 1
        comp = data["competitors"][0]
        assert comp["slug"] == "chatgpt"
        assert "sentiment_score" in comp
        assert "monthly_visits" in comp
        assert "trend" in comp
        assert "hot_events" in comp

        # 验证舆情总览
        sentiment = data["sentiment"]
        assert sentiment["total_mentions"] >= 1
        assert sentiment["positive_pct"] >= 0
        assert sentiment["negative_pct"] >= 0
        assert "trending_topics" in sentiment
        assert "alert_count" in sentiment

        # 验证爬虫状态
        spiders = data["spiders"]
        assert spiders["total_tasks"] >= 1
        assert spiders["success_tasks_24h"] >= 1
        assert "next_scheduled" in spiders

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, client):
        """空数据看板"""
        response = await client.get("/api/v1/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["sentiment"]["total_mentions"] == 0
        assert data["spiders"]["total_tasks"] == 0


@pytest.mark.unit
class TestDashboardWebSocket:
    """WebSocket测试"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, client, auth_token):
        """WebSocket连接认证"""
        import httpx
        from httpx import ASGITransport
        from app.main import create_app
        from app.db.session import get_db

        # 需要直接创建WebSocket连接
        # httpx不支持WebSocket，使用async_client
        # 这里使用测试标记跳过（FastAPI TestClient不支持async WebSocket）
        pytest.skip("WebSocket测试需要专门的async WebSocket客户端")

    def test_websocket_auth_requires_token(self):
        """WebSocket需要token认证"""
        # 验证端点定义中包含token参数
        from app.api.v1.endpoints.dashboard import realtime_websocket
        import inspect
        sig = inspect.signature(realtime_websocket)
        params = list(sig.parameters.keys())
        assert "token" in params
