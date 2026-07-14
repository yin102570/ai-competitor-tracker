"""
爬虫模块 - AI对话产品竞品追踪系统

三引擎架构:
  - BaseSpider:     抽象基类，定义 fetch/parse/save 接口
  - HttpxSpider:    httpx 引擎，用于 API 对接和静态页面
  - PlaywrightSpider: Playwright 引擎，用于 JS 动态页面

业务采集器:
  - CompetitorSpider: 竞品数据采集（定价/功能/排名 -> CompetitorHistory）
  - SentimentSpider:  舆情数据采集（多源社交 -> SentimentRecord）
"""

from app.spiders.base_spider import (
    BaseSpider,
    FetchResult,
    ProxyPool,
    RateLimiter,
    RobotsChecker,
    SpiderConfig,
    USER_AGENTS,
)
from app.spiders.competitor_spider import (
    COMPETITOR_REGISTRY,
    CompetitorSpider,
    PricingPlan,
)
from app.spiders.httpx_spider import HttpxSpider
from app.spiders.playwright_spider import PlaywrightSpider, WaitStrategy
from app.spiders.sentiment_spider import (
    COMPETITOR_KEYWORDS,
    SENTIMENT_SOURCES,
    SentimentSpider,
    SocialPost,
)

__all__ = [
    # 基类与核心组件
    "BaseSpider",
    "SpiderConfig",
    "FetchResult",
    "RateLimiter",
    "ProxyPool",
    "RobotsChecker",
    "USER_AGENTS",
    # 引擎
    "HttpxSpider",
    "PlaywrightSpider",
    "WaitStrategy",
    # 业务采集器
    "CompetitorSpider",
    "COMPETITOR_REGISTRY",
    "PricingPlan",
    "SentimentSpider",
    "SENTIMENT_SOURCES",
    "COMPETITOR_KEYWORDS",
    "SocialPost",
]
