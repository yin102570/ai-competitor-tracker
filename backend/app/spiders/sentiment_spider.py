"""
舆情数据采集器 - 多源社交媒体数据采集 + 情感分析
功能:
  - 从社交媒体（Twitter/Reddit/微博/HackerNews）采集提及目标竞品的帖子
  - 去重（content_hash SHA256）
  - 调用 sentiment_engine 做情感分析
  - 写入 SentimentRecord 表

数据流:
  fetch(多源社交媒体) -> parse(提取帖子) -> save(去重 + 情感分析 + 写入DB)

引擎选择:
  - HackerNews: httpx (Algolia JSON API)
  - Reddit: httpx (.json API)
  - Twitter/X: Playwright (JS渲染必需)
  - 微博: Playwright (JS渲染必需)
"""

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.sentiment import SentimentRecord
from app.services.sentiment_engine import sentiment_engine
from app.spiders.base_spider import BaseSpider, FetchResult, SpiderConfig
from app.spiders.httpx_spider import HttpxSpider
from app.spiders.playwright_spider import PlaywrightSpider

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


# ============================================================
# 社交媒体源配置
# ============================================================

SENTIMENT_SOURCES: dict[str, dict[str, Any]] = {
    "hackernews": {
        "name": "Hacker News",
        "engine": "httpx",
        "search_url": "https://hn.algolia.com/api/v1/search",
        "search_param": "query",
        "tags": "story",
        "hits_per_page": 20,
        "content_field": "title",
        "url_field": "url",
        "date_field": "created_at",
    },
    "reddit": {
        "name": "Reddit",
        "engine": "httpx",
        "search_url": "https://www.reddit.com/search.json",
        "search_param": "q",
        "sort": "relevance",
        "limit": 25,
        "content_field": "title",
        "subreddit_field": "subreddit",
        "date_field": "created_utc",
    },
    "twitter": {
        "name": "Twitter/X",
        "engine": "playwright",
        "search_url": "https://twitter.com/search?q={query}&src=typed_query",
        "wait_until": "networkidle",
        "wait_selector": '[data-testid="tweetText"]',
        "tweet_selector": '[data-testid="tweetText"]',
        "scroll_times": 3,
    },
    "weibo": {
        "name": "微博",
        "engine": "playwright",
        "search_url": "https://s.weibo.com/weibo?q={query}",
        "wait_until": "networkidle",
        "wait_selector": ".card-wrap",
        "post_selector": ".txt[node-type=\"feed_text\"]",
        "scroll_times": 2,
    },
}

# 竞品搜索关键词映射 - 每个竞品在不同平台可能用不同关键词
COMPETITOR_KEYWORDS: dict[str, list[str]] = {
    "chatgpt": ["ChatGPT", "OpenAI", "GPT-4", "GPT-4o"],
    "claude": ["Claude AI", "Anthropic", "Claude 3"],
    "gemini": ["Google Gemini", "Gemini AI", "Bard AI"],
    "copilot": ["GitHub Copilot", "Copilot AI"],
    "perplexity": ["Perplexity AI", "Perplexity"],
    "deepseek": ["DeepSeek", "DeepSeek AI", "深度求索"],
}


# ============================================================
# 帖子数据结构
# ============================================================

class SocialPost:
    """社交媒体帖子（运行时数据结构）"""

    def __init__(
        self,
        source: str,
        content: str,
        url: str = "",
        author: str = "",
        published_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.source = source
        self.content = content.strip()
        self.url = url
        self.author = author
        self.published_at = published_at or datetime.now(CST)
        self.extra = extra or {}

    @property
    def content_hash(self) -> str:
        """计算内容的 SHA256 哈希（用于去重）"""
        # 规范化: 去除首尾空白、统一换行、小写
        normalized = self.content.strip().lower().replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "content_hash": self.content_hash,
            "extra": self.extra,
        }

    def __repr__(self) -> str:
        return (
            f"<SocialPost(source={self.source}, "
            f"content={self.content[:50]}...)>"
        )


# ============================================================
# 舆情采集器
# ============================================================

class SentimentSpider(BaseSpider[list[SocialPost]]):
    """
    舆情数据采集器

    职责:
      1. 从多个社交媒体平台采集提及目标竞品的帖子
      2. 通过 content_hash 去重（避免重复入库）
      3. 调用 sentiment_engine 做情感分析
      4. 将分析结果写入 SentimentRecord 表

    使用示例:
        async with SentimentSpider() as spider:
            # 采集单个竞品在所有平台的舆情
            await spider.crawl_sentiment("chatgpt")
            # 采集单个平台
            await spider.crawl_source("chatgpt", "hackernews")
    """

    def __init__(
        self,
        config: SpiderConfig | None = None,
        session_factory: Any = None,
    ) -> None:
        super().__init__(config)
        self._session_factory = session_factory or async_session_factory
        self._httpx_spider: HttpxSpider | None = None
        self._playwright_spider: PlaywrightSpider | None = None

    # ============================================================
    # 引擎懒加载
    # ============================================================

    async def _get_httpx_spider(self) -> HttpxSpider:
        """获取 httpx 引擎实例（复用）"""
        if self._httpx_spider is None:
            self._httpx_spider = HttpxSpider(self.config)
        return self._httpx_spider

    async def _get_playwright_spider(self) -> PlaywrightSpider:
        """获取 Playwright 引擎实例（复用）"""
        if self._playwright_spider is None:
            self._playwright_spider = PlaywrightSpider(self.config)
            await self._playwright_spider.start()
        return self._playwright_spider

    # ============================================================
    # fetch - 根据来源调度到不同引擎
    # ============================================================

    async def fetch(
        self,
        url: str,
        source: str = "hackernews",
        **kwargs: Any,
    ) -> FetchResult:
        """
        根据数据源选择引擎抓取

        参数:
            url: 目标URL
            source: 数据源标识 (hackernews/reddit/twitter/weibo)

        返回:
            FetchResult 统一结果
        """
        source_config = SENTIMENT_SOURCES.get(source, {})
        engine = source_config.get("engine", "httpx")

        if engine == "playwright":
            spider = await self._get_playwright_spider()
            wait_until = source_config.get("wait_until", "networkidle")
            wait_selector = source_config.get("wait_selector")
            scroll_times = source_config.get("scroll_times", 2)

            # 构建滚动动作序列
            actions: list[dict[str, Any]] = []
            for _ in range(scroll_times):
                actions.append({"type": "scroll", "pixels": 800})
                actions.append({"type": "wait", "ms": 2000})

            # 限速 + 重试由基类的 _do_fetch 处理
            await self._rate_limit()
            return await spider.fetch(
                url,
                wait_until=wait_until,
                wait_selector=wait_selector,
                actions=actions,
            )
        else:
            spider = await self._get_httpx_spider()
            await self._rate_limit()
            return await spider.fetch(url, method="GET")

    # ============================================================
    # parse - 从抓取结果提取帖子
    # ============================================================

    async def parse(
        self,
        result: FetchResult,
        source: str = "hackernews",
        competitor_slug: str = "",
        **kwargs: Any,
    ) -> list[SocialPost]:
        """
        从抓取结果中提取社交媒体帖子

        参数:
            result: fetch 结果
            source: 数据源标识
            competitor_slug: 竞品标识

        返回:
            SocialPost 列表
        """
        if not result.is_success:
            logger.warning(
                f"SentimentSpider.parse: non-success {result.status} "
                f"for {result.url}"
            )
            return []

        source_config = SENTIMENT_SOURCES.get(source, {})
        engine = source_config.get("engine", "httpx")

        if engine == "playwright":
            return await self._parse_playwright_result(
                result, source, source_config
            )
        else:
            return await self._parse_api_result(
                result, source, source_config
            )

    async def _parse_api_result(
        self,
        result: FetchResult,
        source: str,
        source_config: dict[str, Any],
    ) -> list[SocialPost]:
        """解析 JSON API 响应（HackerNews/Reddit）"""
        posts: list[SocialPost] = []

        try:
            data = result.json()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"JSON parse failed for {source}: {exc}")
            return []

        if source == "hackernews":
            hits = data.get("hits", [])
            content_field = source_config.get("content_field", "title")
            url_field = source_config.get("url_field", "url")
            date_field = source_config.get("date_field", "created_at")

            for hit in hits:
                content = hit.get(content_field, "")
                if not content:
                    continue
                post_url = hit.get(url_field, "") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                author = hit.get("author", "")
                created_at = hit.get(date_field)

                published_at = datetime.now(CST)
                if created_at:
                    try:
                        published_at = datetime.fromtimestamp(
                            int(created_at), tz=CST
                        )
                    except (ValueError, TypeError, OSError):
                        pass

                posts.append(SocialPost(
                    source="hackernews",
                    content=content,
                    url=post_url,
                    author=author,
                    published_at=published_at,
                    extra={"points": hit.get("points", 0), "num_comments": hit.get("num_comments", 0)},
                ))

        elif source == "reddit":
            children = (
                data.get("data", {}).get("children", [])
                if isinstance(data, dict)
                else []
            )
            content_field = source_config.get("content_field", "title")
            date_field = source_config.get("date_field", "created_utc")

            for child in children:
                child_data = child.get("data", {})
                content = child_data.get(content_field, "")
                if not content:
                    continue

                # 合并标题和正文
                self_text = child_data.get("selftext", "")
                if self_text:
                    content = f"{content}\n{self_text}"

                post_url = f"https://www.reddit.com{child_data.get('permalink', '')}"
                author = child_data.get("author", "")
                created_utc = child_data.get(date_field)

                published_at = datetime.now(CST)
                if created_utc:
                    try:
                        published_at = datetime.fromtimestamp(
                            float(created_utc), tz=CST
                        )
                    except (ValueError, TypeError, OSError):
                        pass

                posts.append(SocialPost(
                    source="reddit",
                    content=content,
                    url=post_url,
                    author=author,
                    published_at=published_at,
                    extra={
                        "subreddit": child_data.get("subreddit", ""),
                        "score": child_data.get("score", 0),
                        "num_comments": child_data.get("num_comments", 0),
                    },
                ))

        logger.info(f"Parsed {len(posts)} posts from {source}")
        return posts

    async def _parse_playwright_result(
        self,
        result: FetchResult,
        source: str,
        source_config: dict[str, Any],
    ) -> list[SocialPost]:
        """解析 Playwright 渲染后的页面（Twitter/微博）"""
        posts: list[SocialPost] = []
        soup = BeautifulSoup(result.text, "html.parser")

        if source == "twitter":
            tweet_selector = source_config.get(
                "tweet_selector", '[data-testid="tweetText"]'
            )
            tweet_elements = soup.select(tweet_selector)

            for el in tweet_elements:
                content = el.get_text(strip=True)
                if not content or len(content) < 10:
                    continue

                # 尝试提取推文链接
                tweet_link = ""
                parent = el.find_parent("article")
                if parent:
                    link = parent.find("a", href=True)
                    if link and "/status/" in link.get("href", ""):
                        tweet_link = link["href"]

                # 尝试提取作者
                author = ""
                if parent:
                    user_el = parent.select_one('[data-testid="User-Name"]')
                    if user_el:
                        author = user_el.get_text(strip=True)[:50]

                posts.append(SocialPost(
                    source="twitter",
                    content=content,
                    url=tweet_link,
                    author=author,
                    published_at=datetime.now(CST),
                ))

        elif source == "weibo":
            post_selector = source_config.get("post_selector", ".txt")
            post_elements = soup.select(post_selector)

            for el in post_elements:
                content = el.get_text(strip=True)
                if not content or len(content) < 10:
                    continue

                # 尝试提取微博链接
                weibo_link = ""
                parent_card = el.find_parent(class_="card-wrap")
                if parent_card:
                    link = parent_card.find("a", href=True)
                    if link:
                        weibo_link = link.get("href", "")

                posts.append(SocialPost(
                    source="weibo",
                    content=content,
                    url=weibo_link,
                    author="",
                    published_at=datetime.now(CST),
                ))

        logger.info(f"Parsed {len(posts)} posts from {source}")
        return posts

    # ============================================================
    # save - 去重 + 情感分析 + 写入数据库
    # ============================================================

    async def save(
        self,
        data: list[SocialPost],
        competitor_slug: str = "",
        **kwargs: Any,
    ) -> int:
        """
        持久化舆情数据

        流程:
          1. 通过 content_hash 去重（查询DB已有记录）
          2. 对新帖子调用 sentiment_engine 做情感分析
          3. 写入 SentimentRecord 表

        参数:
            data: SocialPost 列表
            competitor_slug: 竞品标识

        返回:
            新写入的记录数
        """
        if not data or not competitor_slug:
            logger.warning("SentimentSpider.save: empty data or missing slug")
            return 0

        # 收集所有 content_hash 用于批量查重
        all_hashes = [post.content_hash for post in data]

        async with self._session_factory() as session:
            try:
                # 查询已存在的 hash
                existing_result = await session.execute(
                    select(SentimentRecord.content_hash).where(
                        SentimentRecord.content_hash.in_(all_hashes)
                    )
                )
                existing_hashes: set[str] = {
                    row[0] for row in existing_result.fetchall()
                }

                # 过滤出新帖子
                new_posts = [
                    post for post in data
                    if post.content_hash not in existing_hashes
                ]

                if not new_posts:
                    logger.info(
                        f"SentimentSpider.save: all {len(data)} posts "
                        f"already exist, skipped"
                    )
                    return 0

                logger.info(
                    f"SentimentSpider.save: {len(new_posts)}/{len(data)} "
                    f"new posts to analyze for {competitor_slug}"
                )

                # 逐条情感分析 + 写入
                saved = 0
                for post in new_posts:
                    try:
                        # 调用情感分析引擎
                        sentiment_result = await sentiment_engine.analyze_text(
                            post.content
                        )

                        # 构建 SentimentRecord
                        record = SentimentRecord(
                            competitor_slug=competitor_slug,
                            source=post.source,
                            content=post.content[:5000],  # 限制长度
                            content_hash=post.content_hash,
                            sentiment_score=sentiment_result.get("score", 0.0),
                            sentiment_label=sentiment_result.get("label", "neutral"),
                            topics=json.dumps(
                                sentiment_result.get("topics", []),
                                ensure_ascii=False,
                            ),
                            published_at=post.published_at,
                        )
                        session.add(record)
                        saved += 1
                    except Exception as exc:
                        logger.error(
                            f"Sentiment analysis failed for post "
                            f"({post.source}): {exc}"
                        )
                        # 跳过情感分析失败的帖子，不中断流程
                        continue

                await session.commit()
                logger.info(
                    f"SentimentSpider.save: saved {saved} records "
                    f"for {competitor_slug}"
                )
                return saved

            except Exception as exc:
                await session.rollback()
                logger.error(
                    f"SentimentSpider.save failed for {competitor_slug}: {exc}"
                )
                raise

    # ============================================================
    # 高级采集方法
    # ============================================================

    async def crawl_source(
        self,
        competitor_slug: str,
        source: str,
    ) -> dict[str, Any]:
        """
        采集单个平台的舆情数据

        参数:
            competitor_slug: 竞品标识
            source: 平台标识 (hackernews/reddit/twitter/weibo)

        返回:
            采集统计信息
        """
        source_config = SENTIMENT_SOURCES.get(source)
        if not source_config:
            return {"error": f"Unknown source: {source}"}

        # 获取搜索关键词
        keywords = COMPETITOR_KEYWORDS.get(competitor_slug, [competitor_slug])
        query = " OR ".join(keywords)

        # 构建搜索URL
        if source == "hackernews":
            url = f"{source_config['search_url']}?{source_config['search_param']}={query}&tags={source_config.get('tags', 'story')}&hitsPerPage={source_config.get('hits_per_page', 20)}"
        elif source == "reddit":
            url = f"{source_config['search_url']}?q={query}&sort={source_config.get('sort', 'relevance')}&limit={source_config.get('limit', 25)}"
        elif source == "twitter":
            url = source_config["search_url"].format(query=query.replace(" OR ", " OR "))
        elif source == "weibo":
            url = source_config["search_url"].format(query=query)
        else:
            url = source_config.get("search_url", "").format(query=query)

        logger.info(f"Crawling {source} for {competitor_slug}: {url}")

        return await self.crawl(
            url,
            source=source,
            competitor_slug=competitor_slug,
        )

    async def crawl_sentiment(
        self,
        competitor_slug: str,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        采集竞品在多个平台的舆情数据

        参数:
            competitor_slug: 竞品标识
            sources: 平台列表，默认全部

        返回:
            各平台采集结果汇总
        """
        if sources is None:
            sources = list(SENTIMENT_SOURCES.keys())

        results: dict[str, Any] = {}
        total_saved = 0

        for source in sources:
            try:
                result = await self.crawl_source(competitor_slug, source)
                results[source] = result
                total_saved += result.get("saved", 0)
            except Exception as exc:
                logger.error(
                    f"Sentiment crawl failed: {competitor_slug}/{source}: {exc}"
                )
                results[source] = {"error": str(exc)}

        results["total_saved"] = total_saved
        return results

    async def crawl_all(
        self,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        采集所有竞品在所有平台的舆情数据

        参数:
            sources: 平台列表，默认全部

        返回:
            各竞品采集结果汇总
        """
        all_results: dict[str, Any] = {}
        for slug in COMPETITOR_KEYWORDS:
            try:
                result = await self.crawl_sentiment(slug, sources)
                all_results[slug] = result
            except Exception as exc:
                logger.error(f"Sentiment crawl failed for {slug}: {exc}")
                all_results[slug] = {"error": str(exc)}
        return all_results

    # ============================================================
    # 资源清理
    # ============================================================

    async def close(self) -> None:
        """关闭所有子引擎"""
        if self._httpx_spider is not None:
            await self._httpx_spider.close()
            self._httpx_spider = None
        if self._playwright_spider is not None:
            await self._playwright_spider.close()
            self._playwright_spider = None
        await super().close()

    # ============================================================
    # 配置查询
    # ============================================================

    @staticmethod
    def get_sources() -> dict[str, dict[str, Any]]:
        """获取所有数据源配置"""
        return dict(SENTIMENT_SOURCES)

    @staticmethod
    def get_keywords(slug: str) -> list[str]:
        """获取竞品的搜索关键词"""
        return COMPETITOR_KEYWORDS.get(slug, [slug])
