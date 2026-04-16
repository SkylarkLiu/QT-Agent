from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.providers.base import BaseLLMProvider
from app.schemas.provider import LLMMessage, LLMResponse, LLMStreamChunk


class GLMProvider(BaseLLMProvider):
    provider_name = "glm"

    def __init__(self) -> None:
        settings = get_settings()
        self.config = settings.llm
        self.base_url = (self.config.base_url or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.timeout = self.config.timeout_seconds

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
            "messages": [message.model_dump(exclude_none=True) for message in messages],
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
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            response.raise_for_status()

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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
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
