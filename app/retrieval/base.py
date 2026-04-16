from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VectorDocument:
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


class BaseVectorStore(ABC):
    @abstractmethod
    async def ensure_collection(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, documents: list[VectorDocument], embeddings: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def similarity_search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorDocument]:
        raise NotImplementedError
