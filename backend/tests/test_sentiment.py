"""
sentiment 模块单元测试
覆盖: 舆情面板、趋势分析、情感分析、热点事件、舆情记录
"""

import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture
async def sample_sentiment_data(db_session):
    """预置测试舆情数据"""
    from app.models.competitor import Competitor
    from app.models.sentiment import SentimentRecord

    # 先创建竞品
    comp = Competitor(
        slug="chatgpt",
        name="ChatGPT",
        company="OpenAI",
        category="chatbot",
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    # 创建舆情记录
    cst = timezone(timedelta(hours=8))
    records = [
        SentimentRecord(
            competitor_slug="chatgpt",
            source="twitter",
            content="ChatGPT is amazing! Love the new features.",
            content_hash="hash1",
            sentiment_score=0.85,
            sentiment_label="positive",
            topics='["功能", "用户体验"]',
            published_at=datetime.now(cst) - timedelta(days=1),
        ),
        SentimentRecord(
            competitor_slug="chatgpt",
            source="reddit",
            content="The pricing is too expensive for what it offers.",
            content_hash="hash2",
            sentiment_score=-0.65,
            sentiment_label="negative",
            topics='["价格"]',
            published_at=datetime.now(cst) - timedelta(days=2),
        ),
        SentimentRecord(
            competitor_slug="chatgpt",
            source="微博",
            content="ChatGPT日常使用中，没什么特别的感受。",
            content_hash="hash3",
            sentiment_score=0.0,
            sentiment_label="neutral",
            topics='["综合评价"]',
            published_at=datetime.now(cst) - timedelta(days=3),
        ),
    ]
    for r in records:
        db_session.add(r)
    await db_session.commit()


@pytest.mark.unit
class TestSentimentDashboard:
    """舆情面板测试"""

    @pytest.mark.asyncio
    async def test_dashboard(self, client, sample_sentiment_data):
        """获取舆情面板"""
        response = await client.get("/api/v1/sentiment/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert "competitors" in data
        assert data["overview"]["total_mentions"] == 3
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, client):
        """空数据面板"""
        response = await client.get("/api/v1/sentiment/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["overview"]["total_mentions"] == 0


@pytest.mark.unit
class TestSentimentTrends:
    """趋势分析测试"""

    @pytest.mark.asyncio
    async def test_trends(self, client, sample_sentiment_data):
        """获取趋势数据"""
        response = await client.get("/api/v1/sentiment/trends")
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "30d"
        assert len(data["data"]) == 31  # 30天+今天
        assert "topics" in data

    @pytest.mark.asyncio
    async def test_trends_by_competitor(self, client, sample_sentiment_data):
        """按竞品筛选趋势"""
        response = await client.get(
            "/api/v1/sentiment/trends",
            params={"competitor_slug": "chatgpt", "days": 7},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "7d"


@pytest.mark.unit
class TestSentimentAnalyze:
    """情感分析测试"""

    @pytest.mark.asyncio
    async def test_analyze_positive(self, client, auth_headers):
        """分析正面文本"""
        response = await client.post(
            "/api/v1/sentiment/analyze",
            json={
                "text": "This product is amazing and works perfectly!",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sentiment_label"] == "positive"
        assert data["sentiment_score"] > 0
        assert data["cost"] == 0.5
        assert "confidence" in data
        assert len(data["topics"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_negative(self, client, auth_headers):
        """分析负面文本"""
        response = await client.post(
            "/api/v1/sentiment/analyze",
            json={
                "text": "Terrible experience, the app crashes constantly and is very slow.",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sentiment_label"] == "negative"
        assert data["sentiment_score"] < 0

    @pytest.mark.asyncio
    async def test_analyze_with_competitor(self, client, auth_headers, sample_sentiment_data):
        """关联竞品分析"""
        response = await client.post(
            "/api/v1/sentiment/analyze",
            json={
                "text": "ChatGPT is really great for coding tasks.",
                "competitor_slug": "chatgpt",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sentiment_label"] == "positive"

    @pytest.mark.asyncio
    async def test_analyze_quota_exceeded(self, client, db_session):
        """配额耗尽应返回403"""
        from app.models.user import User
        from app.core.security import hash_password

        # 创建配额耗尽用户
        user = User(
            email="quota_test@example.com",
            password_hash=hash_password("TestPass123!"),
            name="配额测试",
            role="viewer",
            daily_quota=1,
            quota_used=1,
        )
        db_session.add(user)
        await db_session.commit()

        # 登录
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "quota_test@example.com", "password": "TestPass123!"},
        )
        token = login_resp.json()["access_token"]

        response = await client.post(
            "/api/v1/sentiment/analyze",
            json={"text": "Test text for analysis."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "AUTH_QUOTA_EXCEEDED"


@pytest.mark.unit
class TestSentimentEvents:
    """热点事件测试"""

    @pytest.mark.asyncio
    async def test_get_events(self, client, sample_sentiment_data):
        """获取热点事件"""
        response = await client.get("/api/v1/sentiment/chatgpt/events")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) <= 20

    @pytest.mark.asyncio
    async def test_get_events_nonexistent(self, client):
        """不存在的竞品应返回404"""
        response = await client.get("/api/v1/sentiment/nonexistent/events")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND_COMPETITOR"


@pytest.mark.unit
class TestSentimentRecords:
    """舆情记录列表测试"""

    @pytest.mark.asyncio
    async def test_list_records(self, client, sample_sentiment_data):
        """获取舆情记录列表"""
        response = await client.get("/api/v1/sentiment/records")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_list_records_by_label(self, client, sample_sentiment_data):
        """按情感标签筛选"""
        response = await client.get(
            "/api/v1/sentiment/records",
            params={"sentiment_label": "positive"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["sentiment_label"] == "positive"

    @pytest.mark.asyncio
    async def test_list_records_by_competitor(self, client, sample_sentiment_data):
        """按竞品筛选"""
        response = await client.get(
            "/api/v1/sentiment/records",
            params={"competitor_slug": "chatgpt"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["competitor_slug"] == "chatgpt"

    @pytest.mark.asyncio
    async def test_list_records_pagination(self, client, sample_sentiment_data):
        """分页测试"""
        response = await client.get(
            "/api/v1/sentiment/records",
            params={"page": 1, "page_size": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
