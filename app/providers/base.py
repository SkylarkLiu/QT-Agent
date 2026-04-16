from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.schemas.provider import EmbeddingResult, LLMMessage, LLMResponse, LLMStreamChunk


class BaseLLMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        raise NotImplementedError


class BaseEmbeddingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def embed_documents(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        raise NotImplementedError

    async def embed_query(self, text: str, *, model: str | None = None) -> list[float]:
        result = await self.embed_documents([text], model=model)
        return result.embeddings[0]


class BaseSearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, *, top_k: int = 5, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


@dataclass(slots=True)
class ParsedSection:
    """Parser 输出的一个文本段落。"""

    content: str
    page: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    """Parser 的完整输出。"""

    sections: list[ParsedSection]
    total_pages: int = 0
    source_type: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseParser(ABC):
    """文件解析基类。

    子类需要实现 :meth:`_parse_impl`，返回统一的 ``ParseResult``。
    """

    supported_extensions: list[str] = []

    @abstractmethod
    async def _parse_impl(self, source: bytes, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        raise NotImplementedError

    async def parse(self, source: str | bytes, *, metadata: dict[str, Any] | None = None) -> ParseResult:
        raw = source.encode("utf-8") if isinstance(source, str) else source
        return await self._parse_impl(raw, metadata=metadata)


class BaseSkill(ABC):
    name: str
    description: str

    @abstractmethod
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
