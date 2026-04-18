from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.providers.base import BaseLLMProvider
from app.schemas.provider import LLMMessage, LLMResponse, LLMStreamChunk


class MockLLMProvider(BaseLLMProvider):
    provider_name = "mock"

    def _resolve_model(self, model: str | None) -> str:
        return model or "mock-echo"

    def _render(self, messages: list[LLMMessage | dict[str, Any]]) -> str:
        latest = ""
        for message in reversed(messages):
            if isinstance(message, dict):
                if message.get("role") == "user":
                    latest = str(message.get("content", ""))
                    break
                continue
            if message.role == "user":
                latest = message.content
                break
        return f"[mock] {latest}"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        content = self._render(messages)
        return LLMResponse(
            content=content,
            model=self._resolve_model(model),
            provider=self.provider_name,
            finish_reason="stop",
            usage={"prompt_tokens": len(messages), "completion_tokens": len(content.split())},
            raw={"mode": "mock", "temperature": temperature, "max_tokens": max_tokens, "metadata": metadata or {}},
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
        content = self._render(messages)
        for index, token in enumerate(content.split()):
            yield LLMStreamChunk(
                delta=(token if index == 0 else f" {token}"),
                model=self._resolve_model(model),
                provider=self.provider_name,
                index=index,
                done=False,
                raw={"mode": "mock"},
            )
        yield LLMStreamChunk(
            delta="",
            model=self._resolve_model(model),
            provider=self.provider_name,
            index=len(content.split()),
            finish_reason="stop",
            done=True,
            raw={"mode": "mock"},
        )
