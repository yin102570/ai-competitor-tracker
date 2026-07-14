"""
DeepSeek API 客户端 - 真实API调用
功能: 聊天补全 / JSON结构化输出 / 流式响应
文档: https://api-docs.deepseek.com/
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek API 客户端封装"""

    def __init__(self):
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._model = settings.deepseek_model
        self._timeout = httpx.Timeout(30.0, connect=10.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端（连接复用）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: dict | None = None,
    ) -> dict[str, Any]:
        """
        调用聊天补全接口

        参数:
            messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
            temperature: 0.0-2.0, 越低越确定性
            max_tokens: 最大生成token数
            response_format: {"type": "json_object"} 强制JSON输出

        返回:
            {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}}
        """
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            logger.info(
                f"DeepSeek API called: model={self._model}, "
                f"tokens={usage.get('total_tokens', 'N/A')}"
            )

            return {"content": content, "usage": usage}

        except httpx.HTTPStatusError as exc:
            logger.error(f"DeepSeek API HTTP error: {exc.response.status_code} - {exc.response.text}")
            raise
        except httpx.RequestError as exc:
            logger.error(f"DeepSeek API request error: {exc}")
            raise
        except (KeyError, IndexError) as exc:
            logger.error(f"DeepSeek API response parse error: {exc}")
            raise

    async def chat_completion_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """
        调用聊天补全并解析JSON输出
        自动添加 response_format={"type": "json_object"}
        """
        result = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(result["content"])
            return {"data": parsed, "usage": result["usage"]}
        except json.JSONDecodeError as exc:
            logger.error(f"DeepSeek JSON parse error: {exc}, raw: {result['content'][:200]}")
            raise

    async def close(self) -> None:
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# 全局单例
deepseek_client = DeepSeekClient()
