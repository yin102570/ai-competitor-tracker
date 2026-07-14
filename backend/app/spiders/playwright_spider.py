"""
Playwright 爬虫引擎 - 无头浏览器，用于JS动态页面
适用场景:
  - 抓取需要JavaScript渲染的页面（Twitter/X帖子、Reddit帖子、微博话题）
  - 绕过前端反爬机制（SPA应用、动态加载内容）
  - 模拟用户交互（滚动、点击、等待异步数据）

特点:
  - 无头浏览器配置（stealth模式、反检测脚本注入）
  - 页面等待策略（networkidle / domcontentloaded / load / 自定义selector）
  - 异步上下文管理器（自动管理浏览器生命周期）
  - 代理池支持
"""

import logging
import time
from typing import Any, Literal

from app.spiders.base_spider import BaseSpider, FetchResult, SpiderConfig

logger = logging.getLogger(__name__)

# 页面等待策略类型
WaitStrategy = Literal[
    "load",              # 等待 load 事件
    "domcontentloaded",  # 等待 DOMContentLoaded 事件
    "networkidle",       # 等待网络空闲（500ms内无新请求）
]


# ============================================================
# Stealth 反检测脚本 - 注入到页面中隐藏自动化特征
# ============================================================

STEALTH_SCRIPT: str = """
// 隐藏 webdriver 标志
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// 伪装 plugins 数量
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// 伪装 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'zh-CN'],
});

// 伪装 platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
});

// 移除 Playwright 痕迹
delete window.__playwright;
delete window.__pw_manual;

// 伪装 chrome 对象
window.chrome = {
    runtime: {},
    loadTimes: () => {},
    csi: () => {},
    app: {},
};

// 伪装 permissions API
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""


class PlaywrightSpider(BaseSpider[dict[str, Any]]):
    """
    Playwright 引擎 - 用于JS动态页面抓取

    使用示例（异步上下文管理器）:
        async with PlaywrightSpider(headless=True) as spider:
            result = await spider.fetch(
                "https://twitter.com/...",
                wait_until="networkidle",
            )
            data = await spider.parse(result)

    使用示例（手动管理）:
        spider = PlaywrightSpider()
        await spider.start()
        try:
            result = await spider.fetch(url)
        finally:
            await spider.close()
    """

    def __init__(
        self,
        config: SpiderConfig | None = None,
        headless: bool = True,
        browser_type: str = "chromium",
        viewport: dict[str, int] | None = None,
    ) -> None:
        super().__init__(config)
        self._headless: bool = headless
        self._browser_type: str = browser_type
        self._viewport: dict[str, int] = viewport or {"width": 1920, "height": 1080}

        # Playwright 资源（延迟初始化）
        self._playwright: Any = None  # Playwright 实例
        self._browser: Any = None     # 浏览器实例
        self._context: Any = None     # 浏览器上下文

    # ============================================================
    # 生命周期管理
    # ============================================================

    async def start(self) -> "PlaywrightSpider":
        """启动浏览器（显式调用或通过 __aenter__ 触发）"""
        if self._browser is not None:
            return self  # 已启动

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ImportError(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium"
            ) from exc

        self._playwright = await async_playwright().start()

        # 选择浏览器类型
        browser_launcher = getattr(self._playwright, self._browser_type)
        launch_kwargs: dict[str, Any] = {
            "headless": self._headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        }

        # 代理支持
        proxy = await self._get_proxy()
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
            logger.debug(f"PlaywrightSpider: using proxy {proxy}")

        self._browser = await browser_launcher.launch(**launch_kwargs)

        # 创建浏览器上下文（含stealth配置）
        context_kwargs: dict[str, Any] = {
            "viewport": self._viewport,
            "user_agent": self._pick_user_agent(),
            "locale": "en-US",
            "timezone_id": "Asia/Shanghai",
            "ignore_https_errors": True,
            "java_script_enabled": True,
        }

        self._context = await self._browser.new_context(**context_kwargs)

        # 注入 stealth 反检测脚本
        await self._context.add_init_script(STEALTH_SCRIPT)
        logger.info(
            f"PlaywrightSpider started: {self._browser_type} "
            f"headless={self._headless}"
        )
        return self

    async def close(self) -> None:
        """关闭浏览器及所有资源"""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        await super().close()
        logger.debug("PlaywrightSpider closed")

    async def __aenter__(self) -> "PlaywrightSpider":
        return await self.start()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # ============================================================
    # fetch - 核心抓取方法
    # ============================================================

    async def fetch(
        self,
        url: str,
        wait_until: WaitStrategy = "networkidle",
        wait_selector: str | None = None,
        wait_timeout: float | None = None,
        actions: list[dict[str, Any]] | None = None,
        extra_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> FetchResult:
        """
        使用无头浏览器抓取页面（支持JS渲染）

        参数:
            url: 目标URL
            wait_until: 页面等待策略
                - "load": 等待 load 事件
                - "domcontentloaded": 等待 DOMContentLoaded
                - "networkidle": 等待网络空闲（适合SPA）
            wait_selector: 等待特定CSS选择器出现
            wait_timeout: 等待超时（秒），默认使用 config.timeout
            actions: 页面加载后执行的交互动作序列
                [{"type": "scroll", "pixels": 500},
                 {"type": "click", "selector": "#load-more"},
                 {"type": "wait", "ms": 2000}]
            extra_headers: 额外请求头

        返回:
            FetchResult 统一结果对象
        """
        if self._context is None:
            await self.start()

        timeout_ms = int((wait_timeout or self.config.timeout) * 1000)

        # 创建新页面
        page = await self._context.new_page()

        # 设置额外请求头
        if extra_headers:
            await page.set_extra_http_headers(extra_headers)

        # 拦截不必要的资源（图片、字体等），提升速度
        await page.route(
            "**/*",
            lambda route: self._route_handler(route),
        )

        start = time.monotonic()

        try:
            # 导航到目标URL
            response = await page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout_ms,
            )

            # 等待特定元素出现
            if wait_selector:
                await page.wait_for_selector(
                    wait_selector,
                    timeout=timeout_ms,
                    state="visible",
                )

            # 执行交互动作序列
            if actions:
                await self._execute_actions(page, actions)

            # 获取渲染后的页面内容
            content = await page.content()
            status = response.status if response else 200
            headers = dict(response.headers) if response else {}

            elapsed = time.monotonic() - start

            return FetchResult(
                url=page.url,
                status=status,
                headers=headers,
                text=content,
                content=content.encode("utf-8"),
                elapsed=elapsed,
            )
        finally:
            await page.close()

    # ============================================================
    # 资源路由 - 拦截非必要资源以加速
    # ============================================================

    @staticmethod
    async def _route_handler(route: Any) -> None:
        """拦截图片/字体/媒体资源，仅保留文档/脚本/样式/接口"""
        resource_type = route.request.resource_type
        if resource_type in ("image", "font", "media"):
            await route.abort()
        else:
            await route.continue_()

    # ============================================================
    # 交互动作执行
    # ============================================================

    async def _execute_actions(self, page: Any, actions: list[dict[str, Any]]) -> None:
        """执行页面交互动作序列（滚动/点击/等待/输入）"""
        for action in actions:
            action_type = action.get("type", "")
            try:
                if action_type == "scroll":
                    pixels = action.get("pixels", 500)
                    await page.evaluate(f"window.scrollBy(0, {pixels})")
                elif action_type == "click":
                    selector = action.get("selector", "")
                    await page.click(selector, timeout=5000)
                elif action_type == "wait":
                    ms = action.get("ms", 1000)
                    await page.wait_for_timeout(ms)
                elif action_type == "input":
                    selector = action.get("selector", "")
                    text = action.get("text", "")
                    await page.fill(selector, text)
                elif action_type == "press":
                    key = action.get("key", "Enter")
                    await page.keyboard.press(key)
                else:
                    logger.warning(f"Unknown action type: {action_type}")
            except Exception as exc:
                logger.warning(f"Action '{action_type}' failed: {exc}")

    # ============================================================
    # parse - 默认解析方法
    # ============================================================

    async def parse(
        self,
        result: FetchResult,
        selector: str | None = None,
        extract_mode: str = "html",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        解析Playwright抓取结果
        默认使用HTML解析（BeautifulSoup4）
        """
        from bs4 import BeautifulSoup

        if not result.is_success:
            return {
                "type": "error",
                "status": result.status,
                "url": result.url,
                "data": None,
            }

        if extract_mode == "json":
            import json

            try:
                data = json.loads(result.text)
                return {"type": "json", "data": data, "url": result.url}
            except (json.JSONDecodeError, ValueError):
                pass  # 降级到HTML解析

        # HTML 解析
        soup = BeautifulSoup(result.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        parsed: dict[str, Any] = {
            "type": "html",
            "url": result.url,
            "status": result.status,
            "title": title,
            "data": [],
        }

        if selector:
            elements = soup.select(selector)
            for el in elements:
                item: dict[str, Any] = {"text": el.get_text(strip=True)}
                if el.attrs:
                    item["attrs"] = dict(el.attrs)
                parsed["data"].append(item)
        else:
            # 提取页面关键信息
            parsed["meta_description"] = (
                soup.find("meta", attrs={"name": "description"}) or {}
            ).get("content", "")
            parsed["body_text"] = soup.get_text(strip=True)[:5000]
            parsed["links"] = [
                {"text": a.get_text(strip=True)[:100], "href": a.get("href", "")}
                for a in soup.find_all("a", href=True)[:50]
            ]

        return parsed

    # ============================================================
    # save - 默认空实现
    # ============================================================

    async def save(self, data: dict[str, Any], **kwargs: Any) -> int:
        """默认保存方法 - 子类覆写"""
        logger.info(
            f"PlaywrightSpider.save: type={data.get('type', 'unknown')}"
        )
        return 0

    # ============================================================
    # 便捷方法 - 提取页面文本内容
    # ============================================================

    async def fetch_text(
        self,
        url: str,
        wait_until: WaitStrategy = "networkidle",
        wait_selector: str | None = None,
    ) -> str:
        """
        便捷方法 - 获取渲染后的页面纯文本
        适合快速提取帖子正文内容
        """
        from bs4 import BeautifulSoup

        result = await self._with_retry(
            self._do_fetch,
            url,
            wait_until=wait_until,
            wait_selector=wait_selector,
        )
        self._stats["fetched"] += 1
        soup = BeautifulSoup(result.text, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    async def fetch_html(
        self,
        url: str,
        wait_until: WaitStrategy = "networkidle",
        wait_selector: str | None = None,
    ) -> str:
        """便捷方法 - 获取渲染后的完整HTML"""
        result = await self._with_retry(
            self._do_fetch,
            url,
            wait_until=wait_until,
            wait_selector=wait_selector,
        )
        self._stats["fetched"] += 1
        return result.text

    async def screenshot(
        self,
        url: str,
        path: str,
        full_page: bool = True,
        wait_until: WaitStrategy = "networkidle",
    ) -> str:
        """
        截取页面截图（用于调试和存档）

        参数:
            url: 目标URL
            path: 截图保存路径
            full_page: 是否截取完整页面

        返回:
            截图文件路径
        """
        if self._context is None:
            await self.start()

        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until=wait_until, timeout=self.config.timeout * 1000)
            await page.screenshot(path=path, full_page=full_page)
            logger.info(f"Screenshot saved: {path}")
            return path
        finally:
            await page.close()
