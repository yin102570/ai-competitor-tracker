"""
httpx 爬虫引擎 - 轻量级异步HTTP客户端
适用场景:
  - 抓取竞品官网公开数据（流量排名、产品信息）
  - 调用公开API获取数据（Product Hunt、SimilarWeb公开接口）
  - JSON / HTML 混合解析

特点:
  - 基于 httpx.AsyncClient，原生异步
  - 支持代理池、UA轮换、限速、重试
  - 自动识别响应类型（JSON/HTML），提供对应解析方法
  - 连接池复用，适合批量请求
"""

import json
import logging
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.spiders.base_spider import BaseSpider, FetchResult, SpiderConfig

logger = logging.getLogger(__name__)


class HttpxSpider(BaseSpider[dict[str, Any]]):
    """
    httpx 引擎 - 用于API对接和静态页面抓取

    使用示例:
        async with HttpxSpider() as spider:
            result = await spider.fetch("https://api.example.com/data")
            data = await spider.parse(result)
            await spider.save(data)
    """

    def __init__(
        self,
        config: SpiderConfig | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config)
        self._external_client: httpx.AsyncClient | None = client
        self._client: httpx.AsyncClient | None = None

    # ============================================================
    # httpx 客户端管理
    # ============================================================

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 异步客户端（连接池复用）"""
        if self._external_client is not None:
            return self._external_client

        if self._client is None or self._client.is_closed:
            proxy = await self._get_proxy()
            # 使用代理时跳过SSL验证（代理环境常存在证书问题）
            client_kwargs: dict[str, Any] = {
                "timeout": httpx.Timeout(
                    timeout=self.config.timeout,
                    connect=10.0,
                    read=self.config.timeout,
                    write=10.0,
                    pool=5.0,
                ),
                "follow_redirects": True,
                "headers": self._build_headers(),
                "verify": proxy is None,
            }
            if proxy:
                client_kwargs["proxy"] = proxy
                logger.debug(f"HttpxSpider: using proxy {proxy}")

            self._client = httpx.AsyncClient(**client_kwargs)

        return self._client

    async def close(self) -> None:
        """关闭 httpx 客户端"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        await super().close()

    # ============================================================
    # fetch - 核心抓取方法
    # ============================================================

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | str | None = None,
        json_body: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> FetchResult:
        """
        发送HTTP请求并返回统一 FetchResult

        参数:
            url: 请求URL
            method: HTTP方法 (GET/POST/PUT/DELETE)
            params: 查询参数
            headers: 额外请求头（会与UA轮换头合并）
            body: 请求体（原始字符串或表单）
            json_body: JSON请求体（自动序列化）

        返回:
            FetchResult 统一结果对象
        """
        client = await self._get_client()

        # 合并请求头（每次请求轮换UA）
        final_headers = self._build_headers(headers)

        # 构建请求参数
        request_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "params": params,
            "headers": final_headers,
        }
        if json_body is not None:
            request_kwargs["json"] = json_body
        elif body is not None:
            request_kwargs["content"] = body if isinstance(body, str) else None
            if isinstance(body, dict):
                request_kwargs["data"] = body

        start = time.monotonic()
        response = await client.request(**request_kwargs)
        elapsed = time.monotonic() - start

        # 构建统一结果
        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            headers=dict(response.headers),
            text=response.text,
            content=response.content,
            elapsed=elapsed,
        )

    # ============================================================
    # parse - 默认解析方法（JSON/HTML自动识别）
    # ============================================================

    async def parse(
        self,
        result: FetchResult,
        selector: str | None = None,
        extract_mode: str = "auto",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        解析抓取结果 - 自动识别JSON或HTML

        参数:
            result: fetch 返回的 FetchResult
            selector: CSS选择器（HTML模式时使用）
            extract_mode: "auto" | "json" | "html"

        返回:
            解析后的字典:
            - JSON模式: {"type": "json", "data": {...}}
            - HTML模式: {"type": "html", "data": [...], "title": "..."}
        """
        if not result.is_success:
            logger.warning(
                f"Parse: non-success status {result.status} for {result.url}"
            )
            return {
                "type": "error",
                "status": result.status,
                "url": result.url,
                "data": None,
            }

        # 确定解析模式
        if extract_mode == "auto":
            if result.is_json:
                extract_mode = "json"
            elif result.is_html:
                extract_mode = "html"
            else:
                # 尝试JSON解析，失败则按HTML处理
                try:
                    json.loads(result.text)
                    extract_mode = "json"
                except (json.JSONDecodeError, ValueError):
                    extract_mode = "html"

        if extract_mode == "json":
            return await self.parse_json(result, **kwargs)
        else:
            return await self.parse_html(result, selector=selector, **kwargs)

    async def parse_json(self, result: FetchResult, **kwargs: Any) -> dict[str, Any]:
        """解析JSON响应"""
        try:
            data = result.json()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"JSON parse failed for {result.url}: {exc}")
            return {"type": "json", "data": None, "error": str(exc), "url": result.url}

        return {
            "type": "json",
            "data": data,
            "url": result.url,
            "status": result.status,
        }

    async def parse_html(
        self,
        result: FetchResult,
        selector: str | None = None,
        extract_attrs: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        解析HTML响应（使用BeautifulSoup4）

        参数:
            selector: CSS选择器，用于提取特定元素
            extract_attrs: 需要提取的属性列表（如 ["href", "src", "text"]）
        """
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
                if extract_attrs:
                    for attr in extract_attrs:
                        item[attr] = el.get(attr, "")
                else:
                    # 默认提取所有属性
                    if el.attrs:
                        item["attrs"] = dict(el.attrs)
                parsed["data"].append(item)
        else:
            # 无选择器时提取页面结构摘要
            parsed["meta_description"] = self._extract_meta(soup, "description")
            parsed["meta_keywords"] = self._extract_meta(soup, "keywords")
            parsed["headings"] = self._extract_headings(soup)
            parsed["links"] = self._extract_links(soup)

        return parsed

    # ============================================================
    # HTML 辅助提取方法
    # ============================================================

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, name: str) -> str:
        """提取 meta 标签内容"""
        tag = soup.find("meta", attrs={"name": name})
        if tag:
            return tag.get("content", "")
        # 尝试 Open Graph 协议
        og_tag = soup.find("meta", attrs={"property": f"og:{name}"})
        if og_tag:
            return og_tag.get("content", "")
        return ""

    @staticmethod
    def _extract_headings(soup: BeautifulSoup) -> list[dict[str, str]]:
        """提取页面标题层级"""
        headings: list[dict[str, str]] = []
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(strip=True)
                if text:
                    headings.append({"level": f"h{level}", "text": text})
        return headings

    @staticmethod
    def _extract_links(soup: BeautifulSoup, limit: int = 50) -> list[dict[str, str]]:
        """提取页面链接"""
        links: list[dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            links.append({"text": a.get_text(strip=True)[:100], "href": a["href"]})
            if len(links) >= limit:
                break
        return links

    # ============================================================
    # save - 默认空实现（子类覆写）
    # ============================================================

    async def save(self, data: dict[str, Any], **kwargs: Any) -> int:
        """
        默认保存方法 - 仅记录日志
        子类（如CompetitorSpider）应覆写此方法实现数据库写入
        """
        data_type = data.get("type", "unknown")
        logger.info(
            f"HttpxSpider.save: type={data_type}, "
            f"data_keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}"
        )
        return 0

    # ============================================================
    # 便捷方法 - API调用
    # ============================================================

    async def fetch_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        便捷方法 - 直接获取JSON数据
        内部完成 fetch + parse，跳过 save
        """
        result = await self._with_retry(
            self._do_fetch,
            url,
            method="GET",
            params=params,
            headers=headers,
        )
        self._stats["fetched"] += 1
        if not result.is_success:
            raise httpx.HTTPStatusError(
                f"HTTP {result.status}",
                request=httpx.Request("GET", url),
                response=httpx.Response(result.status),
            )
        parsed = await self.parse_json(result)
        return parsed

    async def fetch_html(
        self,
        url: str,
        selector: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        便捷方法 - 直接获取HTML并解析
        内部完成 fetch + parse，跳过 save
        """
        result = await self._with_retry(
            self._do_fetch,
            url,
            method="GET",
            headers=headers,
        )
        self._stats["fetched"] += 1
        parsed = await self.parse_html(result, selector=selector)
        return parsed
