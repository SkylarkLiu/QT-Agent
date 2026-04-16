from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseLLMProvider
from app.schemas.provider import LLMMessage, LLMResponse, LLMStreamChunk

logger = get_logger("app.providers.glm")

# 429 重试配置
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # 秒
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class GLMProvider(BaseLLMProvider):
    provider_name = "glm"

    def __init__(self) -> None:
        settings = get_settings()
        self.config = settings.llm
        self.base_url = (self.config.base_url or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.timeout = self.config.timeout

    def _resolve_model(self, model: str | None) -> str:
        return model or self.config.model

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise ValueError("GLM API key is not configured. Set LLM__API_KEY before calling the GLM provider.")
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._resolve_model(model),
            "messages": [
                (message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else message)
                for message in messages
            ],
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if metadata:
            payload["metadata"] = metadata
        return payload

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload = self._payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            metadata=metadata,
        )
        response = await self._request_with_retry(
            client_post=lambda client: client.post(
                f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
            )
        )

        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return LLMResponse(
            content=message.get("content", ""),
            model=data.get("model") or self._resolve_model(model),
            provider=self.provider_name,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage") or {},
            raw=data,
        )

    async def _request_with_retry(self, client_post, max_retries: int = _MAX_RETRIES) -> httpx.Response:
        """带指数退避重试的 HTTP 请求，处理 429/5xx 限流和服务端错误。"""
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client_post(client)
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response

                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                retry_after = float(response.headers.get("Retry-After", 0))
                backoff = max(retry_after, _INITIAL_BACKOFF * (_BACKOFF_FACTOR ** (attempt - 1)))
                logger.warning(
                    "glm.rate_limited",
                    extra={
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "backoff": backoff,
                    },
                )
                if attempt < max_retries:
                    await asyncio.sleep(backoff)

        raise last_exc  # type: ignore[misc]

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = self._payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            metadata=metadata,
        )

        # 流式请求也先建立连接（带重试），然后迭代 chunk
        stream_ctx = await self._stream_connect_with_retry(payload)
        async with stream_ctx as response:
            index = 0
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data_line = line.removeprefix("data:").strip()
                if data_line == "[DONE]":
                    yield LLMStreamChunk(
                        delta="",
                        model=self._resolve_model(model),
                        provider=self.provider_name,
                        index=index,
                        finish_reason="stop",
                        done=True,
                    )
                    break

                chunk = json.loads(data_line)
                choice = (chunk.get("choices") or [{}])[0]
                delta = (choice.get("delta") or {}).get("content", "")
                finish_reason = choice.get("finish_reason")
                done = finish_reason is not None
                yield LLMStreamChunk(
                    delta=delta,
                    model=chunk.get("model") or self._resolve_model(model),
                    provider=self.provider_name,
                    index=index,
                    finish_reason=finish_reason,
                    done=done,
                    raw=chunk,
                )
                index += 1

    async def _stream_connect_with_retry(self, payload: dict, max_retries: int = _MAX_RETRIES):
        """建立流式连接（带重试），返回 stream context manager。"""
        from contextlib import asynccontextmanager

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            client = httpx.AsyncClient(timeout=self.timeout)
            try:
                stream_cm = client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response = await stream_cm.__aenter__()
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    retry_after = float(response.headers.get("Retry-After", 0))
                    backoff = max(retry_after, _INITIAL_BACKOFF * (_BACKOFF_FACTOR ** (attempt - 1)))
                    logger.warning(
                        "glm.stream_rate_limited",
                        extra={
                            "status_code": response.status_code,
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "backoff": backoff,
                        },
                    )
                    await stream_cm.__aexit__(None, None, None)
                    await client.aclose()
                    if attempt < max_retries:
                        await asyncio.sleep(backoff)
                    continue

                # 成功 — 包装成自管理 context manager
                _response = response
                _client = client

                @asynccontextmanager
                async def _wrapped():
                    try:
                        yield _response
                    finally:
                        await _client.aclose()

                return _wrapped()
            except Exception:
                await client.aclose()
                raise

        raise last_exc  # type: ignore[misc]
