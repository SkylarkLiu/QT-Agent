from __future__ import annotations

import hashlib
import math

from app.core.config import get_settings
from app.providers.base import BaseEmbeddingProvider
from app.schemas.provider import EmbeddingResult


class DefaultEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "default"

    def __init__(self) -> None:
        settings = get_settings()
        self.config = settings.embedding
        self.dimensions = settings.embedding.dimension

    def _resolve_model(self, model: str | None) -> str:
        return model or self.config.model

    def _embed_text(self, text: str) -> list[float]:
        # Deterministic local embedding placeholder so downstream retrieval flows can be developed
        # before wiring a remote embedding service.
        vector = [0.0] * self.dimensions
        if not text:
            return vector

        for token in text.split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dimensions):
                vector[i] += digest[i % len(digest)] / 255.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def embed_documents(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        embeddings = [self._embed_text(text) for text in texts]
        return EmbeddingResult(
            provider=self.provider_name,
            model=self._resolve_model(model),
            embeddings=embeddings,
            dimensions=self.dimensions,
            raw={"count": len(texts), "mode": "deterministic-local"},
        )
