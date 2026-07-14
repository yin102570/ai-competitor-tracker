"""
competitors 模块单元测试
覆盖: 列表/详情/创建/更新/删除/历史查询/对标分析/权限校验
"""

import pytest


@pytest.fixture
async def sample_competitors(db_session):
    """预置测试竞品数据"""
    from app.models.competitor import Competitor

    competitors_data = [
        {
            "slug": "chatgpt",
            "name": "ChatGPT",
            "company": "OpenAI",
            "category": "chatbot",
            "website": "https://chat.openai.com",
        },
        {
            "slug": "claude",
            "name": "Claude",
            "company": "Anthropic",
            "category": "chatbot",
            "website": "https://claude.ai",
        },
        {
            "slug": "gemini",
            "name": "Gemini",
            "company": "Google",
            "category": "multimodal",
            "website": "https://gemini.google.com",
        },
    ]
    for data in competitors_data:
        comp = Competitor(**data)
        db_session.add(comp)
    await db_session.commit()


@pytest.mark.unit
class TestCompetitorList:
    """竞品列表测试"""

    @pytest.mark.asyncio
    async def test_list_competitors(self, client, sample_competitors):
        """获取竞品列表"""
        response = await client.get("/api/v1/competitors/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 1
        assert data["items"][0]["slug"] in ["chatgpt", "claude", "gemini"]

    @pytest.mark.asyncio
    async def test_list_by_category(self, client, sample_competitors):
        """按分类筛选"""
        response = await client.get(
            "/api/v1/competitors/",
            params={"category": "chatbot"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "chatbot"

    @pytest.mark.asyncio
    async def test_list_pagination(self, client, sample_competitors):
        """分页参数"""
        response = await client.get(
            "/api/v1/competitors/",
            params={"page": 1, "page_size": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2


@pytest.mark.unit
class TestCompetitorDetail:
    """竞品详情测试"""

    @pytest.mark.asyncio
    async def test_get_competitor_detail(self, client, sample_competitors):
        """获取竞品详情"""
        response = await client.get("/api/v1/competitors/chatgpt")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "chatgpt"
        assert data["name"] == "ChatGPT"
        assert data["company"] == "OpenAI"

    @pytest.mark.asyncio
    async def test_get_nonexistent_competitor(self, client):
        """不存在的竞品应返回404"""
        response = await client.get("/api/v1/competitors/nonexistent")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND_COMPETITOR"


@pytest.mark.unit
class TestCompetitorCRUD:
    """竞品CRUD测试"""

    @pytest.mark.asyncio
    async def test_create_competitor(self, client, auth_headers):
        """创建竞品"""
        response = await client.post(
            "/api/v1/competitors/",
            json={
                "slug": "deepseek",
                "name": "DeepSeek",
                "company": "DeepSeek",
                "category": "chatbot",
                "website": "https://chat.deepseek.com",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "deepseek"
        assert data["name"] == "DeepSeek"

    @pytest.mark.asyncio
    async def test_create_duplicate_competitor(self, client, auth_headers, sample_competitors):
        """重复slug应返回409"""
        response = await client.post(
            "/api/v1/competitors/",
            json={
                "slug": "chatgpt",
                "name": "ChatGPT Clone",
                "company": "Clone Inc",
                "category": "chatbot",
            },
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONFLICT_DUPLICATE"

    @pytest.mark.asyncio
    async def test_update_competitor(self, client, auth_headers, sample_competitors):
        """更新竞品信息"""
        response = await client.put(
            "/api/v1/competitors/chatgpt",
            json={"name": "ChatGPT Plus"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "ChatGPT Plus"

    @pytest.mark.asyncio
    async def test_delete_competitor(self, client, auth_headers, sample_competitors):
        """删除竞品"""
        response = await client.delete(
            "/api/v1/competitors/claude",
            headers=auth_headers,
        )
        assert response.status_code == 200

        # 确认已删除
        resp2 = await client.get("/api/v1/competitors/claude")
        assert resp2.status_code == 404


@pytest.mark.unit
class TestCompetitorCompare:
    """竞品对标测试"""

    @pytest.mark.asyncio
    async def test_compare_competitors(self, client, auth_headers, sample_competitors):
        """对标分析"""
        response = await client.post(
            "/api/v1/competitors/compare",
            json={
                "slugs": ["chatgpt", "claude"],
                "metrics": ["web_traffic", "model_rank"],
                "time_range": "30d",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cost"] == 5.0
        assert len(data["competitors"]) == 2
        assert "report_id" in data

    @pytest.mark.asyncio
    async def test_compare_single_slug_fails(self, client, auth_headers):
        """对标至少2个竞品"""
        response = await client.post(
            "/api/v1/competitors/compare",
            json={"slugs": ["chatgpt"], "metrics": ["web_traffic"]},
            headers=auth_headers,
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestCompetitorPricing:
    """定价信息测试"""

    @pytest.mark.asyncio
    async def test_get_pricing(self, client, sample_competitors):
        """获取定价信息"""
        response = await client.get("/api/v1/competitors/chatgpt/pricing")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "chatgpt"
