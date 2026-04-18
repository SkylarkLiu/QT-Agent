from __future__ import annotations

from app.core.config import get_settings
from app.providers.base import BaseEmbeddingProvider, BaseLLMProvider, BaseSearchProvider
from app.providers.default_embedding import DefaultEmbeddingProvider
from app.providers.glm import GLMProvider
from app.providers.mock import MockLLMProvider
from app.providers.web_search import TavilySearchProvider
from app.retrieval.base import BaseVectorStore
from app.retrieval.milvus_store import get_milvus_store


class LLMProviderFactory:
    _providers: dict[str, type[BaseLLMProvider]] = {
        "glm": GLMProvider,
    }

    @classmethod
    def create(cls, provider_name: str | None = None, *, model: str | None = None) -> BaseLLMProvider:
        settings = get_settings()
        resolved = (provider_name or settings.llm.provider).lower()
        if model and model.lower().startswith("mock"):
            return MockLLMProvider()
        if resolved == "glm" and not settings.llm.api_key and settings.app.env != "production":
            return MockLLMProvider()
        if resolved not in cls._providers:
            raise ValueError(f"Unsupported LLM provider: {resolved}")
        return cls._providers[resolved]()

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseLLMProvider]) -> None:
        cls._providers[name.lower()] = provider_cls


class EmbeddingProviderFactory:
    _providers: dict[str, type[BaseEmbeddingProvider]] = {
        "default": DefaultEmbeddingProvider,
    }

    @classmethod
    def create(cls, provider_name: str | None = None) -> BaseEmbeddingProvider:
        settings = get_settings()
        resolved = (provider_name or settings.embedding.provider).lower()
        if resolved not in cls._providers:
            raise ValueError(f"Unsupported embedding provider: {resolved}")
        return cls._providers[resolved]()


class VectorStoreFactory:
    @staticmethod
    def create(name: str | None = None) -> BaseVectorStore:
        resolved = (name or "milvus").lower()
        if resolved != "milvus":
            raise ValueError(f"Unsupported vector store: {resolved}")
        return get_milvus_store()


class SearchProviderFactory:
    _providers: dict[str, type[BaseSearchProvider]] = {
        "tavily": TavilySearchProvider,
    }

    @classmethod
    def create(cls, provider_name: str | None = None) -> BaseSearchProvider:
        settings = get_settings()
        resolved = (provider_name or settings.web_search.provider).lower()
        if resolved not in cls._providers:
            raise ValueError(f"Unsupported search provider: {resolved}")
        return cls._providers[resolved]()

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseSearchProvider]) -> None:
        cls._providers[name.lower()] = provider_cls
