"""
爬虫基类 - 定义统一接口规范 (fetch / parse / save)
内置机制: 重试(最多3次) / 限速(每秒N请求) / User-Agent轮换 / 代理池 / robots.txt遵守
所有具体爬虫引擎继承此类

设计原则:
- 模板方法模式: run() 编排 fetch -> parse -> save 完整流程
- 策略模式: 限速/代理/UA 等策略可独立替换
- 开闭原则: 新增引擎只需继承并实现三个抽象方法
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Generic, TypeVar
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from app.core.config import settings

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

# ============================================================
# User-Agent 轮换池 - 覆盖主流浏览器/平台组合
# ============================================================

USER_AGENTS: list[str] = [
    # Chrome - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
    "Gecko/20100101 Firefox/133.0",
    # Firefox - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:133.0) "
    "Gecko/20100101 Firefox/133.0",
    # Safari - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    # Edge - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome - Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

T = TypeVar("T")


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class SpiderConfig:
    """
    爬虫运行配置
    所有参数均可通过 SpiderConfig.from_settings() 从全局配置加载
    """

    rate_limit_per_sec: int = 2
    max_retries: int = 3
    retry_backoff_factor: float = 1.5
    retry_base_delay: float = 1.0
    timeout: float = 30.0
    respect_robots: bool = True
    proxy_pool_url: str = ""
    user_agents: list[str] = field(default_factory=lambda: list(USER_AGENTS))
    default_headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> "SpiderConfig":
        """从全局 settings 构建配置"""
        return cls(
            rate_limit_per_sec=settings.spider_rate_limit_per_sec,
            max_retries=3,
            timeout=30.0,
            respect_robots=True,
            proxy_pool_url=settings.spider_proxy_pool_url,
        )


@dataclass
class FetchResult:
    """统一抓取结果 - 无论底层引擎是 httpx 还是 Playwright"""

    url: str
    status: int
    headers: dict[str, str]
    text: str
    content: bytes
    elapsed: float
    fetched_at: datetime = field(default_factory=lambda: datetime.now(CST))

    @property
    def is_success(self) -> bool:
        """HTTP 2xx 视为成功"""
        return 200 <= self.status < 300

    @property
    def is_json(self) -> bool:
        """响应是否为 JSON 格式"""
        content_type = self.headers.get("content-type", "")
        return "application/json" in content_type.lower()

    @property
    def is_html(self) -> bool:
        """响应是否为 HTML 格式"""
        content_type = self.headers.get("content-type", "")
        return "text/html" in content_type.lower()

    def json(self) -> Any:
        """解析为 JSON（若失败抛出异常）"""
        import json

        return json.loads(self.text)


# ============================================================
# 限速器 - 令牌桶算法，控制每秒请求数
# ============================================================

class RateLimiter:
    """
    异步限速器 - 确保请求间隔不小于 1/rate 秒
    线程安全（使用 asyncio.Lock）
    """

    def __init__(self, rate_per_sec: int) -> None:
        self._rate = max(rate_per_sec, 1)
        self._min_interval = 1.0 / self._rate
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """获取请求许可，必要时等待"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                logger.debug(f"RateLimiter: waiting {wait:.3f}s")
                await asyncio.sleep(wait)
            self._last_request_time = time.monotonic()

    @property
    def rate(self) -> int:
        return self._rate


# ============================================================
# 代理池 - 从远程URL获取代理列表，轮换使用
# ============================================================

class ProxyPool:
    """
    代理池管理器
    - 从 SPIDER_PROXY_POOL_URL 拉取代理列表
    - 轮询(round-robin)分配代理
    - 定时刷新（默认5分钟）
    """

    REFRESH_INTERVAL: int = 300  # 5分钟刷新一次

    def __init__(self, pool_url: str) -> None:
        self._pool_url = pool_url
        self._proxies: list[str] = []
        self._index: int = 0
        self._lock = asyncio.Lock()
        self._last_refresh: float = 0.0

    async def get_proxy(self) -> str | None:
        """
        获取一个代理地址
        返回格式: "http://ip:port" 或 "socks5://ip:port"
        无可用代理时返回 None
        """
        if not self._pool_url:
            return None

        await self._maybe_refresh()

        async with self._lock:
            if not self._proxies:
                return None
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy

    async def _maybe_refresh(self) -> None:
        """按需刷新代理列表"""
        now = time.monotonic()
        if self._proxies and (now - self._last_refresh) < self.REFRESH_INTERVAL:
            return

        async with self._lock:
            # 双重检查
            if self._proxies and (now - self._last_refresh) < self.REFRESH_INTERVAL:
                return
            await self._refresh()

    async def _refresh(self) -> None:
        """从远程URL拉取代理列表"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._pool_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        self._proxies = [str(p) for p in data]
                    elif isinstance(data, dict):
                        self._proxies = [
                            str(p) for p in data.get("proxies", data.get("data", []))
                        ]
                    self._last_refresh = time.monotonic()
                    logger.info(
                        f"ProxyPool refreshed: {len(self._proxies)} proxies"
                    )
                else:
                    logger.warning(
                        f"ProxyPool refresh failed: HTTP {resp.status_code}"
                    )
        except Exception as exc:
            logger.warning(f"ProxyPool refresh error: {exc}")


# ============================================================
# robots.txt 检查器 - 缓存每个域名的规则
# ============================================================

class RobotsChecker:
    """
    robots.txt 检查器
    - 缓存每个域名的 RobotFileParser 实例
    - 异步加载（网络IO在线程池中执行，不阻塞事件循环）
    """

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser | None] = {}
        self._loading: dict[str, asyncio.Event] = {}

    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """检查是否允许抓取指定URL"""
        parsed = urlparse(url)
        domain_key = f"{parsed.scheme}://{parsed.netloc}"

        # 命中缓存
        if domain_key in self._cache:
            rp = self._cache[domain_key]
            if rp is None:
                return True  # 无 robots.txt，默认允许
            return rp.can_fetch(user_agent, url)

        # 防止并发重复加载
        if domain_key in self._loading:
            event = self._loading[domain_key]
            await event.wait()
            rp = self._cache.get(domain_key)
            if rp is None:
                return True
            return rp.can_fetch(user_agent, url)

        # 首次加载
        self._loading[domain_key] = asyncio.Event()
        try:
            rp = await self._load_robots(domain_key)
            self._cache[domain_key] = rp
        finally:
            self._loading[domain_key].set()
            del self._loading[domain_key]

        if rp is None:
            return True
        return rp.can_fetch(user_agent, url)

    async def _load_robots(self, domain: str) -> RobotFileParser | None:
        """异步加载 robots.txt（在线程池中执行同步的 read()）"""
        robots_url = f"{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            await asyncio.to_thread(rp.read)
            logger.debug(f"RobotsChecker: loaded {robots_url}")
            return rp
        except Exception as exc:
            logger.debug(f"RobotsChecker: no robots.txt at {robots_url}: {exc}")
            return None


# ============================================================
# 爬虫基类
# ============================================================

class BaseSpider(ABC, Generic[T]):
    """
    爬虫基类 - 定义 fetch / parse / save 三段式接口

    子类必须实现:
        fetch(url)  -> FetchResult   # 抓取网络资源
        parse(result) -> T           # 解析为结构化数据
        save(data)   -> int          # 持久化，返回写入条数

    内置能力:
        - 重试机制: 最多 max_retries 次，指数退避
        - 限速: 每秒最多 rate_limit_per_sec 个请求
        - UA轮换: 每次请求随机选择 User-Agent
        - 代理池: 从 SPIDER_PROXY_POOL_URL 获取代理
        - robots.txt: 默认遵守，可配置忽略
    """

    def __init__(self, config: SpiderConfig | None = None) -> None:
        self.config: SpiderConfig = config or SpiderConfig.from_settings()
        self._rate_limiter: RateLimiter = RateLimiter(self.config.rate_limit_per_sec)
        self._proxy_pool: ProxyPool = ProxyPool(self.config.proxy_pool_url)
        self._robots_checker: RobotsChecker = RobotsChecker()
        self._stats: dict[str, Any] = {
            "fetched": 0,
            "parsed": 0,
            "saved": 0,
            "errors": 0,
            "retries": 0,
            "robots_blocked": 0,
        }
        self._closed: bool = False

    # ============================================================
    # User-Agent 轮换
    # ============================================================

    def _pick_user_agent(self) -> str:
        """随机选择一个 User-Agent"""
        return random.choice(self.config.user_agents)

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """构建请求头（含轮换UA）"""
        headers: dict[str, str] = {
            "User-Agent": self._pick_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        headers.update(self.config.default_headers)
        if extra:
            headers.update(extra)
        return headers

    # ============================================================
    # 代理获取
    # ============================================================

    async def _get_proxy(self) -> str | None:
        """从代理池获取一个代理"""
        return await self._proxy_pool.get_proxy()

    # ============================================================
    # robots.txt 检查
    # ============================================================

    async def _check_robots(self, url: str) -> bool:
        """
        检查 robots.txt 是否允许抓取
        配置 respect_robots=False 时跳过检查
        """
        if not self.config.respect_robots:
            return True
        allowed = await self._robots_checker.can_fetch(
            url, self._pick_user_agent()
        )
        if not allowed:
            self._stats["robots_blocked"] += 1
            logger.warning(f"Robots.txt disallows: {url}")
        return allowed

    # ============================================================
    # 限速
    # ============================================================

    async def _rate_limit(self) -> None:
        """请求前调用，确保不超速"""
        await self._rate_limiter.acquire()

    # ============================================================
    # 重试机制
    # ============================================================

    async def _with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        带重试的异步调用
        - 最多 max_retries 次尝试
        - 指数退避: base_delay * (backoff_factor ** attempt)
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                self._stats["retries"] += 1
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (
                        self.config.retry_backoff_factor ** (attempt - 1)
                    )
                    # 加入随机抖动，避免惊群
                    jitter = random.uniform(0, delay * 0.3)
                    total_delay = delay + jitter
                    logger.warning(
                        f"Retry {attempt}/{self.config.max_retries} "
                        f"failed: {exc}, retrying in {total_delay:.1f}s"
                    )
                    await asyncio.sleep(total_delay)
                else:
                    logger.error(
                        f"All {self.config.max_retries} attempts failed: {exc}"
                    )
        assert last_exc is not None
        raise last_exc

    # ============================================================
    # 抽象接口 - 子类必须实现
    # ============================================================

    @abstractmethod
    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        """抓取指定URL，返回统一 FetchResult"""
        ...

    @abstractmethod
    async def parse(self, result: FetchResult, **kwargs: Any) -> T:
        """解析 FetchResult 为结构化数据"""
        ...

    @abstractmethod
    async def save(self, data: T, **kwargs: Any) -> int:
        """持久化解析结果，返回写入条数"""
        ...

    # ============================================================
    # 模板方法 - 编排完整流程
    # ============================================================

    async def crawl(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """
        执行完整抓取流程: fetch -> parse -> save
        包含重试、限速、robots检查

        返回统计信息字典
        """
        start = time.monotonic()
        spider_name = self.__class__.__name__
        logger.info(f"[{spider_name}] Starting crawl: {url}")

        # robots.txt 检查
        if not await self._check_robots(url):
            logger.warning(f"[{spider_name}] Blocked by robots.txt: {url}")
            return {**self._stats, "url": url, "blocked": True}

        try:
            # fetch（带重试）
            result = await self._with_retry(self._do_fetch, url, **kwargs)
            self._stats["fetched"] += 1
            logger.info(
                f"[{spider_name}] Fetched: {url} "
                f"status={result.status} elapsed={result.elapsed:.2f}s"
            )

            # parse
            data = await self.parse(result, **kwargs)
            self._stats["parsed"] += 1

            # save
            saved = await self.save(data, **kwargs)
            self._stats["saved"] += saved

            elapsed = time.monotonic() - start
            logger.info(
                f"[{spider_name}] Completed: {url} "
                f"in {elapsed:.2f}s, saved={saved}"
            )
            return {
                **self._stats,
                "url": url,
                "elapsed": round(elapsed, 2),
                "blocked": False,
            }
        except Exception as exc:
            self._stats["errors"] += 1
            logger.error(f"[{spider_name}] Crawl failed: {url} - {exc}")
            raise

    async def _do_fetch(self, url: str, **kwargs: Any) -> FetchResult:
        """内部fetch包装 - 加入限速"""
        await self._rate_limit()
        return await self.fetch(url, **kwargs)

    # ============================================================
    # 资源清理
    # ============================================================

    async def close(self) -> None:
        """释放资源（子类可覆写）"""
        self._closed = True

    async def __aenter__(self) -> "BaseSpider[T]":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # ============================================================
    # 统计信息
    # ============================================================

    @property
    def stats(self) -> dict[str, Any]:
        """获取运行统计"""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """重置统计计数器"""
        self._stats = {
            "fetched": 0,
            "parsed": 0,
            "saved": 0,
            "errors": 0,
            "retries": 0,
            "robots_blocked": 0,
        }
