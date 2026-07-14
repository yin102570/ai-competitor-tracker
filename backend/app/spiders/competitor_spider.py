"""
竞品数据采集器 - 继承 HttpxSpider
功能:
  - 各竞品（ChatGPT/Claude/Gemini等）的官网数据采集
  - 定价页面解析
  - 功能特性提取
  - 写入 CompetitorHistory 表

数据流:
  fetch(官网/定价页) -> parse(定价/功能/排名) -> save(CompetitorHistory + 更新Competitor)
"""

import json
import logging
import re
from datetime import date, datetime, timezone, timedelta
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.competitor import Competitor, CompetitorHistory
from app.spiders.base_spider import FetchResult, SpiderConfig
from app.spiders.httpx_spider import HttpxSpider

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


# ============================================================
# 竞品注册表 - 预置主流AI对话产品配置
# ============================================================

COMPETITOR_REGISTRY: dict[str, dict[str, Any]] = {
    "chatgpt": {
        "name": "ChatGPT",
        "company": "OpenAI",
        "category": "chatbot",
        "website": "https://chat.openai.com",
        "pricing_url": "https://openai.com/chatgpt/pricing/",
        "pricing_selector": "[data-testid*='price'], .pricing-card, .plan-card, "
            ".tier, [class*='price']",
        "features_selector": "ul li, .feature-list li, .feature-item",
        "arena_url": "https://chat.lmsys.org",
    },
    "claude": {
        "name": "Claude",
        "company": "Anthropic",
        "category": "chatbot",
        "website": "https://claude.ai",
        "pricing_url": "https://www.anthropic.com/pricing",
        "pricing_selector": ".pricing-card, .plan, [class*='price'], "
            ".tier-card",
        "features_selector": ".feature, .feature-list li, ul li",
        "arena_url": "https://chat.lmsys.org",
    },
    "gemini": {
        "name": "Gemini",
        "company": "Google",
        "category": "multimodal",
        "website": "https://gemini.google.com",
        "pricing_url": "https://ai.google.dev/pricing",
        "pricing_selector": ".price-card, .pricing-tier, [class*='price'], "
            ".plan-card",
        "features_selector": ".feature, ul li, .feature-list li",
        "arena_url": "https://chat.lmsys.org",
    },
    "copilot": {
        "name": "GitHub Copilot",
        "company": "GitHub/Microsoft",
        "category": "coding",
        "website": "https://github.com/features/copilot",
        "pricing_url": "https://github.com/features/copilot",
        "pricing_selector": ".pricing-card, .plan, [class*='price']",
        "features_selector": ".feature, ul li",
        "arena_url": "https://chat.lmsys.org",
    },
    "perplexity": {
        "name": "Perplexity",
        "company": "Perplexity AI",
        "category": "search",
        "website": "https://www.perplexity.ai",
        "pricing_url": "https://www.perplexity.ai/pricing",
        "pricing_selector": ".pricing-card, .plan, [class*='price']",
        "features_selector": ".feature, ul li",
        "arena_url": "https://chat.lmsys.org",
    },
    "deepseek": {
        "name": "DeepSeek",
        "company": "DeepSeek",
        "category": "chatbot",
        "website": "https://www.deepseek.com",
        "pricing_url": "https://www.deepseek.com/pricing",
        "pricing_selector": ".pricing-card, .plan, [class*='price']",
        "features_selector": ".feature, ul li",
        "arena_url": "https://chat.lmsys.org",
    },
}


# ============================================================
# 定价方案数据结构
# ============================================================

class PricingPlan:
    """定价方案（运行时数据结构）"""

    def __init__(
        self,
        name: str,
        price: str,
        period: str = "month",
        features: list[str] | None = None,
    ) -> None:
        self.name = name
        self.price = price
        self.period = period
        self.features = features or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "price": self.price,
            "period": self.period,
            "features": self.features,
        }

    def __repr__(self) -> str:
        return f"<PricingPlan(name={self.name}, price={self.price})>"


class CompetitorSpider(HttpxSpider):
    """
    竞品数据采集器

    职责:
      1. 采集竞品官网公开数据（流量、产品信息）
      2. 解析定价页面，提取各方案价格和功能
      3. 提取产品功能特性
      4. 将快照写入 CompetitorHistory 表
      5. 更新 Competitor.pricing_info

    使用示例:
        async with CompetitorSpider() as spider:
            # 采集单个竞品定价
            await spider.crawl_pricing("chatgpt")
            # 采集所有竞品
            await spider.crawl_all()
    """

    def __init__(
        self,
        config: SpiderConfig | None = None,
        session_factory: Any = None,
    ) -> None:
        super().__init__(config)
        self._session_factory = session_factory or async_session_factory

    # ============================================================
    # fetch - 继承自 HttpxSpider，无需覆写
    # ============================================================

    # ============================================================
    # parse - 竞品页面解析
    # ============================================================

    async def parse(
        self,
        result: FetchResult,
        parse_type: str = "pricing",
        competitor_slug: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        解析竞品页面

        参数:
            result: fetch 结果
            parse_type: "pricing" | "features" | "website" | "arena"
            competitor_slug: 竞品标识

        返回:
            解析后的结构化数据
        """
        if not result.is_success:
            logger.warning(
                f"CompetitorSpider.parse: non-success {result.status} "
                f"for {result.url}"
            )
            return {
                "type": parse_type,
                "competitor_slug": competitor_slug,
                "url": result.url,
                "data": None,
                "error": f"HTTP {result.status}",
            }

        if parse_type == "pricing":
            return await self._parse_pricing(result, competitor_slug)
        elif parse_type == "features":
            return await self._parse_features(result, competitor_slug)
        elif parse_type == "arena":
            return await self._parse_arena(result, competitor_slug)
        else:
            return await self._parse_website(result, competitor_slug)

    async def _parse_pricing(
        self, result: FetchResult, competitor_slug: str
    ) -> dict[str, Any]:
        """解析定价页面"""
        soup = BeautifulSoup(result.text, "html.parser")
        registry = COMPETITOR_REGISTRY.get(competitor_slug, {})
        selector = registry.get("pricing_selector", "[class*='price']")

        plans: list[dict[str, Any]] = []
        pricing_cards = soup.select(selector)

        for card in pricing_cards:
            plan = self._extract_pricing_from_element(card)
            if plan and plan["name"]:
                plans.append(plan)

        # 降级: 尝试从全文中提取价格信息
        if not plans:
            plans = self._extract_pricing_from_text(result.text)

        return {
            "type": "pricing",
            "competitor_slug": competitor_slug,
            "url": result.url,
            "plans": plans,
            "plan_count": len(plans),
        }

    @staticmethod
    def _extract_pricing_from_element(el: Any) -> dict[str, Any] | None:
        """从单个定价卡片元素提取方案信息"""
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 3:
            return None

        # 提取方案名称（通常是卡片标题或第一个标题标签）
        name = ""
        heading = el.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
        if heading:
            name = heading.get_text(strip=True)

        # 提取价格（匹配 $XX, ¥XX, 免费, Free 等模式）
        price_patterns = [
            r"[\$€£¥]\s*(\d+(?:\.\d+)?)",  # $20, ¥9.9
            r"(\d+(?:\.\d+)?)\s*/\s*(?:month|mo|月)",  # 20/month
            r"(free|免费|Free)",  # Free, 免费
        ]
        price = ""
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price = match.group(0).strip()
                break

        # 提取功能列表
        features: list[str] = []
        for li in el.find_all("li"):
            feat = li.get_text(strip=True)
            if feat and len(feat) < 200:
                features.append(feat)

        if not name and not price:
            return None

        return {
            "name": name or "Unknown",
            "price": price or "N/A",
            "period": "month",
            "features": features[:10],
        }

    @staticmethod
    def _extract_pricing_from_text(text: str) -> list[dict[str, Any]]:
        """从全文降级提取价格信息"""
        plans: list[dict[str, Any]] = []
        # 匹配常见定价模式
        price_matches = re.findall(
            r"[\$¥€£]\s*(\d+(?:\.\d+)?)\s*(?:/mo|/month|每月|/月)?",
            text,
        )
        for i, price in enumerate(price_matches[:5]):
            plans.append({
                "name": f"Plan {i + 1}",
                "price": f"${price}",
                "period": "month",
                "features": [],
            })
        return plans

    async def _parse_features(
        self, result: FetchResult, competitor_slug: str
    ) -> dict[str, Any]:
        """解析功能特性页面"""
        soup = BeautifulSoup(result.text, "html.parser")
        registry = COMPETITOR_REGISTRY.get(competitor_slug, {})
        selector = registry.get("features_selector", "ul li")

        features: list[str] = []
        elements = soup.select(selector)
        for el in elements:
            text = el.get_text(strip=True)
            if text and 5 < len(text) < 200:
                features.append(text)

        return {
            "type": "features",
            "competitor_slug": competitor_slug,
            "url": result.url,
            "features": features[:30],
            "feature_count": len(features),
        }

    async def _parse_website(
        self, result: FetchResult, competitor_slug: str
    ) -> dict[str, Any]:
        """解析官网首页，提取产品概述"""
        soup = BeautifulSoup(result.text, "html.parser")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")
        elif soup.find("meta", attrs={"property": "og:description"}):
            description = soup.find(
                "meta", attrs={"property": "og:description"}
            ).get("content", "")

        return {
            "type": "website",
            "competitor_slug": competitor_slug,
            "url": result.url,
            "title": title,
            "description": description,
        }

    async def _parse_arena(
        self, result: FetchResult, competitor_slug: str
    ) -> dict[str, Any]:
        """解析 Chatbot Arena 排名数据"""
        # Arena 数据通常为 JSON API 响应
        try:
            data = result.json()
        except (json.JSONDecodeError, ValueError):
            # 降级: 从HTML中提取
            soup = BeautifulSoup(result.text, "html.parser")
            text = soup.get_text()
            score_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ELO|elo|score)", text)
            rank_match = re.search(r"#?(\d+)\s*(?:rank|排名)", text, re.IGNORECASE)
            return {
                "type": "arena",
                "competitor_slug": competitor_slug,
                "url": result.url,
                "arena_score": float(score_match.group(1)) if score_match else None,
                "arena_rank": int(rank_match.group(1)) if rank_match else None,
            }

        # 从JSON中查找排名数据
        arena_score: float | None = None
        arena_rank: int | None = None

        if isinstance(data, dict):
            arena_score = data.get("arena_score") or data.get("score") or data.get("elo")
            arena_rank = data.get("arena_rank") or data.get("rank")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get("name", "").lower()
                    comp_name = COMPETITOR_REGISTRY.get(
                        competitor_slug, {}
                    ).get("name", "").lower()
                    if comp_name and comp_name in name:
                        arena_score = item.get("score") or item.get("arena_score")
                        arena_rank = item.get("rank") or item.get("arena_rank")
                        break

        return {
            "type": "arena",
            "competitor_slug": competitor_slug,
            "url": result.url,
            "arena_score": float(arena_score) if arena_score else None,
            "arena_rank": int(arena_rank) if arena_rank else None,
        }

    # ============================================================
    # save - 写入数据库
    # ============================================================

    async def save(self, data: dict[str, Any], **kwargs: Any) -> int:
        """
        将解析结果持久化到数据库

        - pricing 类型: 更新 Competitor.pricing_info
        - arena 类型: 写入 CompetitorHistory (arena_score/rank)
        - 其他: 记录日志
        """
        data_type = data.get("type", "unknown")
        competitor_slug = data.get("competitor_slug", "")

        if not competitor_slug:
            logger.warning("CompetitorSpider.save: missing competitor_slug")
            return 0

        async with self._session_factory() as session:
            saved = 0
            try:
                if data_type == "pricing":
                    saved = await self._save_pricing(
                        session, competitor_slug, data
                    )
                elif data_type == "arena":
                    saved = await self._save_arena_history(
                        session, competitor_slug, data
                    )
                elif data_type == "features":
                    saved = await self._save_features(
                        session, competitor_slug, data
                    )
                else:
                    logger.info(
                        f"CompetitorSpider.save: type={data_type}, "
                        f"no DB write needed"
                    )

                await session.commit()
                logger.info(
                    f"CompetitorSpider.save: {competitor_slug}/{data_type} "
                    f"saved {saved} records"
                )
                return saved
            except Exception as exc:
                await session.rollback()
                logger.error(
                    f"CompetitorSpider.save failed: {competitor_slug}/{data_type}: {exc}"
                )
                raise

    async def _save_pricing(
        self,
        session: AsyncSession,
        competitor_slug: str,
        data: dict[str, Any],
    ) -> int:
        """保存定价信息到 Competitor.pricing_info 字段"""
        result = await session.execute(
            select(Competitor).where(Competitor.slug == competitor_slug)
        )
        competitor = result.scalar_one_or_none()
        if competitor is None:
            logger.warning(f"Competitor not found: {competitor_slug}")
            return 0

        plans = data.get("plans", [])
        pricing_info = {
            "plans": [p if isinstance(p, dict) else p.to_dict() for p in plans],
            "plan_count": len(plans),
            "updated_at": datetime.now(CST).isoformat(),
            "source_url": data.get("url", ""),
        }

        # pricing_info 是 Text 字段，存储 JSON 字符串
        competitor.pricing_info = json.dumps(pricing_info, ensure_ascii=False)
        await session.flush()
        return 1

    async def _save_arena_history(
        self,
        session: AsyncSession,
        competitor_slug: str,
        data: dict[str, Any],
    ) -> int:
        """保存 Arena 排名到 CompetitorHistory"""
        arena_score = data.get("arena_score")
        arena_rank = data.get("arena_rank")

        if arena_score is None and arena_rank is None:
            logger.info("No arena data to save")
            return 0

        # 检查今天是否已有记录
        today = date.today()
        result = await session.execute(
            select(CompetitorHistory).where(
                CompetitorHistory.competitor_slug == competitor_slug,
                CompetitorHistory.date == today,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # 更新今日记录
            if arena_score is not None:
                existing.arena_score = arena_score
            if arena_rank is not None:
                existing.arena_rank = arena_rank
        else:
            # 创建新记录
            history = CompetitorHistory(
                competitor_slug=competitor_slug,
                date=today,
                arena_score=arena_score,
                arena_rank=arena_rank,
            )
            session.add(history)

        await session.flush()
        return 1

    async def _save_features(
        self,
        session: AsyncSession,
        competitor_slug: str,
        data: dict[str, Any],
    ) -> int:
        """保存功能特性（更新 Competitor.pricing_info 的 features 字段）"""
        result = await session.execute(
            select(Competitor).where(Competitor.slug == competitor_slug)
        )
        competitor = result.scalar_one_or_none()
        if competitor is None:
            return 0

        features = data.get("features", [])

        # 合并到现有 pricing_info
        existing_pricing: dict[str, Any] = {}
        if competitor.pricing_info:
            try:
                if isinstance(competitor.pricing_info, str):
                    existing_pricing = json.loads(competitor.pricing_info)
                elif isinstance(competitor.pricing_info, dict):
                    existing_pricing = competitor.pricing_info
            except (json.JSONDecodeError, TypeError):
                existing_pricing = {}

        existing_pricing["features"] = features
        existing_pricing["feature_count"] = len(features)
        existing_pricing["features_updated_at"] = datetime.now(CST).isoformat()

        competitor.pricing_info = json.dumps(existing_pricing, ensure_ascii=False)
        await session.flush()
        return 1

    # ============================================================
    # 高级采集方法
    # ============================================================

    async def crawl_pricing(self, competitor_slug: str) -> dict[str, Any]:
        """
        采集单个竞品的定价信息

        参数:
            competitor_slug: 竞品标识（如 chatgpt, claude）

        返回:
            采集统计信息
        """
        registry = COMPETITOR_REGISTRY.get(competitor_slug)
        if not registry:
            logger.error(f"Unknown competitor: {competitor_slug}")
            return {"error": f"Unknown competitor: {competitor_slug}"}

        pricing_url = registry["pricing_url"]
        logger.info(f"Crawling pricing for {competitor_slug}: {pricing_url}")

        return await self.crawl(
            pricing_url,
            parse_type="pricing",
            competitor_slug=competitor_slug,
        )

    async def crawl_features(self, competitor_slug: str) -> dict[str, Any]:
        """采集单个竞品的功能特性"""
        registry = COMPETITOR_REGISTRY.get(competitor_slug)
        if not registry:
            return {"error": f"Unknown competitor: {competitor_slug}"}

        website = registry["website"]
        logger.info(f"Crawling features for {competitor_slug}: {website}")

        return await self.crawl(
            website,
            parse_type="features",
            competitor_slug=competitor_slug,
        )

    async def crawl_arena_rank(self, competitor_slug: str) -> dict[str, Any]:
        """采集 Chatbot Arena 排名数据"""
        registry = COMPETITOR_REGISTRY.get(competitor_slug)
        if not registry:
            return {"error": f"Unknown competitor: {competitor_slug}"}

        arena_url = registry.get("arena_url", "https://chat.lmsys.org")
        logger.info(f"Crawling arena rank for {competitor_slug}: {arena_url}")

        return await self.crawl(
            arena_url,
            parse_type="arena",
            competitor_slug=competitor_slug,
        )

    async def crawl_website(self, competitor_slug: str) -> dict[str, Any]:
        """采集竞品官网首页概述"""
        registry = COMPETITOR_REGISTRY.get(competitor_slug)
        if not registry:
            return {"error": f"Unknown competitor: {competitor_slug}"}

        website = registry["website"]
        logger.info(f"Crawling website for {competitor_slug}: {website}")

        return await self.crawl(
            website,
            parse_type="website",
            competitor_slug=competitor_slug,
        )

    async def crawl_all(self, task_types: list[str] | None = None) -> dict[str, Any]:
        """
        批量采集所有注册竞品

        参数:
            task_types: 采集类型列表 ["pricing", "features", "arena"]
                        默认全部采集
        """
        if task_types is None:
            task_types = ["pricing", "features"]

        results: dict[str, Any] = {}
        for slug in COMPETITOR_REGISTRY:
            slug_results: dict[str, Any] = {}
            for task_type in task_types:
                try:
                    if task_type == "pricing":
                        result = await self.crawl_pricing(slug)
                    elif task_type == "features":
                        result = await self.crawl_features(slug)
                    elif task_type == "arena":
                        result = await self.crawl_arena_rank(slug)
                    else:
                        continue
                    slug_results[task_type] = result
                except Exception as exc:
                    logger.error(
                        f"Crawl failed: {slug}/{task_type}: {exc}"
                    )
                    slug_results[task_type] = {"error": str(exc)}
            results[slug] = slug_results

        return results

    async def crawl_competitor(
        self,
        competitor_slug: str,
        task_type: str = "pricing",
    ) -> dict[str, Any]:
        """
        通用入口 - 根据任务类型调度采集

        参数:
            competitor_slug: 竞品标识
            task_type: "pricing" | "features" | "arena" | "website"

        返回:
            采集统计信息
        """
        dispatch: dict[str, Any] = {
            "pricing": self.crawl_pricing,
            "features": self.crawl_features,
            "arena": self.crawl_arena_rank,
            "website": self.crawl_website,
        }

        handler = dispatch.get(task_type)
        if handler is None:
            return {"error": f"Unknown task_type: {task_type}"}

        return await handler(competitor_slug)

    # ============================================================
    # 注册表查询
    # ============================================================

    @staticmethod
    def get_registry() -> dict[str, dict[str, Any]]:
        """获取竞品注册表"""
        return dict(COMPETITOR_REGISTRY)

    @staticmethod
    def get_competitor_info(slug: str) -> dict[str, Any] | None:
        """获取单个竞品配置"""
        return COMPETITOR_REGISTRY.get(slug)
