from __future__ import annotations

import asyncio
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, MilvusClient, connections, utility

from app.core.config import get_settings
from app.core.logging import get_logger
from app.retrieval.base import BaseVectorStore, VectorDocument


logger = get_logger("app.retrieval.milvus")
_store: "MilvusStore | None" = None


def _build_filter(metadata_filter: dict[str, Any] | None) -> str | None:
    if not metadata_filter:
        return None

    clauses: list[str] = []
    for key, value in metadata_filter.items():
        if isinstance(value, str):
            clauses.append(f'metadata["{key}"] == "{value}"')
        elif isinstance(value, bool):
            clauses.append(f'metadata["{key}"] == {str(value).lower()}')
        else:
            clauses.append(f'metadata["{key}"] == {value}')
    return " and ".join(clauses)


class MilvusStore(BaseVectorStore):
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.collection_name = settings.milvus.collection
        self.dimension = settings.embedding.dimension

        self.client = MilvusClient(
            uri=settings.milvus.uri,
            user=settings.milvus.user or "",
            password=settings.milvus.password or "",
            db_name=settings.milvus.database,
            token=None,
        )

    async def ensure_collection(self) -> None:
        await asyncio.to_thread(self._ensure_collection_sync)
        logger.info("milvus.collection_ready", extra={"service_name": self.collection_name})

    def _ensure_collection_sync(self) -> None:
        alias = "default"
        connections.connect(
            alias=alias,
            uri=self.settings.milvus.uri,
            user=self.settings.milvus.user or "",
            password=self.settings.milvus.password or "",
            db_name=self.settings.milvus.database,
        )

        if utility.has_collection(self.collection_name, using=alias):
            collection = Collection(self.collection_name, using=alias)
            if not collection.has_index():
                collection.create_index(
                    field_name="embedding",
                    index_params={"index_type": self.settings.milvus.index_type, "metric_type": self.settings.milvus.metric_type},
                )
            collection.load()
            return

        schema = CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64, auto_id=False),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ],
            description="QT-Agent knowledge vectors",
            enable_dynamic_field=False,
        )
        collection = Collection(name=self.collection_name, schema=schema, using=alias)
        collection.create_index(
            field_name="embedding",
            index_params={"index_type": self.settings.milvus.index_type, "metric_type": self.settings.milvus.metric_type},
        )
        collection.load()

    async def upsert(self, documents: list[VectorDocument], embeddings: list[list[float]]) -> None:
        data = [
            {
                "id": document.id,
                "content": document.content,
                "metadata": document.metadata,
                "embedding": embedding,
            }
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        await asyncio.to_thread(self.client.upsert, collection_name=self.collection_name, data=data)
        await asyncio.to_thread(self.client.flush, collection_name=self.collection_name)

    async def similarity_search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorDocument]:
        results = await asyncio.to_thread(
            self.client.search,
            collection_name=self.collection_name,
            data=[query_vector],
            limit=top_k,
            filter=_build_filter(metadata_filter),
            output_fields=["content", "metadata"],
        )

        hits = results[0] if len(results) > 0 else []
        return [
            VectorDocument(
                id=hit["id"],
                content=hit.get("entity", {}).get("content", ""),
                metadata=hit.get("entity", {}).get("metadata") or {},
                score=float(hit["distance"]),
            )
            for hit in hits
        ]



def get_milvus_store() -> MilvusStore:
    global _store
    if _store is None:
        _store = MilvusStore()
    return _store


async def initialize_milvus() -> None:
    await get_milvus_store().ensure_collection()
