"""Retriever: 封装向量检索逻辑，支持 top-k、metadata filter 和用户可见范围过滤。"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.factories import EmbeddingProviderFactory
from app.retrieval.base import VectorDocument
from app.retrieval.milvus_store import get_milvus_store

logger = get_logger("app.retrieval.retriever")


class Retriever:
    """面向业务层的统一检索入口。

    职责：
    1. 对 query 做 embedding
    2. 拼接用户权限 metadata filter（owner_user_id）
    3. 调用 Milvus similarity_search
    4. 返回带 score 的 VectorDocument 列表
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.default_top_k = 5
        self.relevance_threshold = getattr(settings, "rag", None)
        self.relevance_threshold = (
            self.relevance_threshold.relevance_threshold if self.relevance_threshold else 0.5
        )
        self.vector_store = get_milvus_store()
        self.embedding_provider = EmbeddingProviderFactory.create()

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        user_id: str | None = None,
        kb_ids: list[str] | None = None,
        extra_filter: dict[str, Any] | None = None,
    ) -> list[VectorDocument]:
        """检索与 query 最相关的文档片段。

        Args:
            query: 用户自然语言查询
            top_k: 返回条数，默认 5
            user_id: 当前用户 ID，用于权限过滤
            kb_ids: 限定知识库范围
            extra_filter: 额外 metadata 过滤条件

        Returns:
            按 score 降序排列的 VectorDocument 列表
        """
        top_k = top_k or self.default_top_k

        # 1. Embedding query
        query_vector = await self.embedding_provider.embed_query(query)
        logger.info(
            "retriever.embed_query",
            extra={
                "query_length": len(query),
                "dimension": len(query_vector),
            },
        )

        # 2. 构建权限 filter
        metadata_filter = self._build_filter(user_id=user_id, kb_ids=kb_ids, extra=extra_filter)

        # 3. 向量检索
        docs = await self.vector_store.similarity_search(
            query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter or None,
        )
        logger.info(
            "retriever.search_done",
            extra={
                "top_k": top_k,
                "returned": len(docs),
                "has_filter": metadata_filter is not None,
            },
        )
        return docs

    @staticmethod
    def _build_filter(
        *,
        user_id: str | None = None,
        kb_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """组合 metadata 过滤条件。"""
        filters: dict[str, Any] = {}
        if user_id:
            filters["owner_user_id"] = user_id
        if kb_ids:
            filters["kb_id"] = kb_ids  # Milvus JSON field 支持 list contains
        if extra:
            filters.update(extra)
        return filters


# 模块级单例
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
