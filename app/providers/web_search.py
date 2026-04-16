"""WebSearch Provider：基于 Tavily API 的联网搜索实现。

支持的搜索引擎：
- tavily: Tavily Search API（AI 优化搜索，默认）
- 后续可扩展 serpapi / bing / duckduckgo 等
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseSearchProvider

logger = get_logger("app.providers.web_search")


class TavilySearchProvider(BaseSearchProvider):
    """Tavily Search API 实现。

    文档: https://docs.tavily.com/documentation/api-reference/search
    """

    provider_name = "tavily"

    def __init__(self) -> None:
        settings = get_settings()
        self.config = settings.web_search
        self.base_url = self.config.base_url.rstrip("/")
        self.api_key = self.config.api_key
        self.timeout = self.config.timeout_seconds

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """调用 Tavily Search API 获取搜索结果。

        Args:
            query: 搜索查询
            top_k: 返回结果数量上限
            metadata: 额外参数（search_depth, include_answer 等）

        Returns:
            标准化的搜索结果列表，每项包含:
            - title: 结果标题
            - url: 原始链接
            - content: 摘要内容
            - score: 相关度分数
            - raw: 原始 API 返回数据
        """
        if not self.api_key:
            logger.warning("web_search.missing_api_key | Tavily API key is not configured")
            return []

        start = time.perf_counter()
        search_depth = (metadata or {}).get("search_depth", self.config.search_depth)
        include_answer = (metadata or {}).get("include_answer", self.config.include_answer)

        payload: dict[str, Any] = {
            "query": query,
            "max_results": min(top_k, self.config.max_results),
            "search_depth": search_depth,
            "include_answer": include_answer,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "web_search.api_error",
                extra={
                    "status_code": e.response.status_code,
                    "query": query[:50],
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            return []
        except httpx.RequestError as e:
            logger.error(
                "web_search.request_error",
                extra={
                    "error": str(e),
                    "query": query[:50],
                },
            )
            return []

        data = response.json()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        # 标准化结果
        results: list[dict[str, Any]] = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
                "raw": item,
            })

        # Tavily 可能有直接生成的答案
        tavily_answer = data.get("answer", "")

        logger.info(
            "web_search.search",
            extra={
                "provider": self.provider_name,
                "query": query[:50],
                "result_count": len(results),
                "has_answer": bool(tavily_answer),
                "latency_ms": elapsed_ms,
            },
        )

        # 如果 Tavily 直接给了答案，附带在 metadata 中
        if tavily_answer:
            return [{"title": "Tavily AI Answer", "url": "", "content": tavily_answer, "score": 1.0, "raw": {"type": "direct_answer"}}] + results

        return results
