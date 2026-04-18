from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseLLMProvider
from app.providers.mock import MockLLMProvider
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
        self.timeout = httpx.Timeout(self.config.timeout_seconds, connect=10.0)

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
        # 构建消息列表，排除空的 metadata 字段（GLM API 对此敏感）
        formatted_messages = []
        for message in messages:
            if hasattr(message, "model_dump"):
                msg_dict = message.model_dump(exclude_none=True)
                # 移除空的 metadata 字段，避免 GLM API 流式响应异常
                if msg_dict.get("metadata") == {}:
                    msg_dict.pop("metadata")
            else:
                msg_dict = message
            formatted_messages.append(msg_dict)

        payload: dict[str, Any] = {
            "model": self._resolve_model(model),
            "messages": formatted_messages,
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
        resolved_model = self._resolve_model(model)
        try:
            return await self._chat_once(
                messages,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata,
            )
        except Exception:
            if model and model != self.config.model:
                logger.warning(
                    "glm.model_fallback",
                    extra={"requested_model": model, "fallback_model": self.config.model},
                    exc_info=True,
                )
                return await self._chat_once(
                    messages,
                    model=self.config.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    metadata=metadata,
                )
            if get_settings().app.env != "production":
                logger.warning("glm.provider_fallback_to_mock", exc_info=True)
                return await MockLLMProvider().chat(
                    messages,
                    model="mock-echo",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    metadata=metadata,
                )
            raise

    async def _chat_once(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        temperature: float | None,
        max_tokens: int | None,
        metadata: dict[str, Any] | None,
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
            model=data.get("model") or model,
            provider=self.provider_name,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage") or {},
            raw=data,
        )

    async def _request_with_retry(self, client_post, max_retries: int = _MAX_RETRIES) -> httpx.Response:
        """带指数退避重试的 HTTP 请求，处理 429/5xx 限流、ReadTimeout 和网络错误。"""
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client_post(client)
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                    last_exc = exc
                    backoff = _INITIAL_BACKOFF * (_BACKOFF_FACTOR ** (attempt - 1))
                    logger.warning(
                        "glm.timeout_retry",
                        extra={
                            "error": str(exc),
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "backoff": backoff,
                        },
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(backoff)
                    continue

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
        resolved_model = self._resolve_model(model)
        try:
            async for chunk in self._stream_once(
                messages,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata,
            ):
                yield chunk
            return
        except Exception:
            if model and model != self.config.model:
                logger.warning(
                    "glm.stream_model_fallback",
                    extra={"requested_model": model, "fallback_model": self.config.model},
                    exc_info=True,
                )
                async for chunk in self._stream_once(
                    messages,
                    model=self.config.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    metadata=metadata,
                ):
                    yield chunk
                return
            if get_settings().app.env != "production":
                logger.warning("glm.stream_provider_fallback_to_mock", exc_info=True)
                async for chunk in MockLLMProvider().stream_chat(
                    messages,
                    model="mock-echo",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    metadata=metadata,
                ):
                    yield chunk
                return
            raise

    async def _stream_once(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        temperature: float | None,
        max_tokens: int | None,
        metadata: dict[str, Any] | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = self._payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            metadata=metadata,
        )
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        if response.status_code in _RETRYABLE_STATUS_CODES:
                            retry_after = float(response.headers.get("Retry-After", 0))
                            backoff = max(retry_after, _INITIAL_BACKOFF * (_BACKOFF_FACTOR ** (attempt - 1)))
                            logger.warning(
                                "glm.stream_rate_limited",
                                extra={
                                    "status_code": response.status_code,
                                    "attempt": attempt,
                                    "max_retries": _MAX_RETRIES,
                                    "backoff": backoff,
                                },
                            )
                            if attempt < _MAX_RETRIES:
                                await asyncio.sleep(backoff)
                                continue
                            response.raise_for_status()

                        index = 0
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue

                            data_line = line.removeprefix("data:").strip()
                            if data_line == "[DONE]":
                                yield LLMStreamChunk(
                                    delta="",
                                    model=model,
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
                                model=chunk.get("model") or model,
                                provider=self.provider_name,
                                index=index,
                                finish_reason=finish_reason,
                                done=done,
                                raw=chunk,
                            )
                            index += 1
                        return
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ReadError) as exc:
                    last_exc = exc
                    backoff = _INITIAL_BACKOFF * (_BACKOFF_FACTOR ** (attempt - 1))
                    logger.warning(
                        "glm.stream_timeout_retry",
                        extra={
                            "error": str(exc),
                            "attempt": attempt,
                            "max_retries": _MAX_RETRIES,
                            "backoff": backoff,
                        },
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(backoff)
                        continue
        raise last_exc  # type: ignore[misc]
