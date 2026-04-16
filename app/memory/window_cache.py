"""WindowCacheService — 相似问题缓存命中。

在 Redis 热窗口中存储历史 query 的 embedding，
当新问题到来时，先做 embedding 比对：
  - cosine similarity >= threshold → 命中缓存，直接复用回答
  - 否则走正常 LLM 流程

与 check_window_cache 的关系：
  - check_window_cache 做精确 query 匹配（同一问题字面相同）
  - WindowCacheService 做语义相似匹配（措辞不同但语义相近）
  - 两者互补：精确匹配在前，语义匹配在后
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.cache.redis_client import build_window_cache_key, get_json, get_redis, set_json
from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.factories import EmbeddingProviderFactory

logger = get_logger("app.memory.cache")


@dataclass(slots=True)
class CacheHit:
    """缓存命中结果。"""

    query: str
    response_text: str
    similarity: float
    route_type: str
    provider: str
    usage: dict


class WindowCacheService:
    """相似问题缓存服务。

    工作流程：
    1. check_exact_hit() — 精确匹配（从 query_cache key）
    2. check_similarity_hit() — 语义匹配（embedding cosine similarity）
    3. save_cache() — 保存当前 query + embedding 到窗口
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.similarity_threshold = settings.memory.cache_similarity_threshold
        self.candidate_limit = settings.memory.cache_candidate_limit

    # ------------------------------------------------------------------
    # 精确匹配
    # ------------------------------------------------------------------

    async def check_exact_hit(
        self,
        session_id: str,
        normalized_query: str,
        *,
        user_id: str | None = None,
    ) -> CacheHit | None:
        """精确匹配：query 字面相同则命中。"""
        settings = get_settings()
        cache_key = f"{settings.cache.prefix}:query_cache:{session_id}:{normalized_query}"
        cached = await get_json(cache_key)
        if cached and cached.get("query") == normalized_query:
            return CacheHit(
                query=normalized_query,
                response_text=cached.get("response_text", ""),
                similarity=1.0,
                route_type=cached.get("route_type", "smalltalk"),
                provider=cached.get("provider", "cache"),
                usage=cached.get("usage", {}),
            )
        return None

    # ------------------------------------------------------------------
    # 语义相似匹配
    # ------------------------------------------------------------------

    async def check_similarity_hit(
        self,
        session_id: str,
        normalized_query: str,
        *,
        user_id: str | None = None,
    ) -> CacheHit | None:
        """语义相似匹配：embedding cosine similarity >= threshold 则命中。

        流程：
        1. 对当前 query 做 embedding
        2. 从 Redis 获取窗口中的历史 queries + embeddings
        3. 计算 cosine similarity
        4. 最高分 >= threshold 则返回缓存命中
        """
        # 1. 获取当前 query 的 embedding
        provider = EmbeddingProviderFactory.create()
        result = await provider.embed_documents([normalized_query])
        if not result.embeddings or not result.embeddings[0]:
            logger.debug("cache.embedding_failed")
            return None
        query_embedding = result.embeddings[0]

        # 2. 从 Redis 获取窗口中的历史 query embeddings
        window_key = self._build_embeddings_key(session_id, user_id=user_id)
        cached_queries = await get_json(window_key)
        if not cached_queries or not isinstance(cached_queries, list):
            return None

        # 只取最近 N 条
        candidates = cached_queries[-self.candidate_limit:]

        # 3. 计算 cosine similarity
        best_score = -1.0
        best_entry: dict[str, Any] | None = None

        for entry in candidates:
            cached_emb = entry.get("embedding")
            if not cached_emb or len(cached_emb) != len(query_embedding):
                continue

            score = self._cosine_similarity(query_embedding, cached_emb)
            if score > best_score:
                best_score = score
                best_entry = entry

        # 4. 判断是否达到阈值
        if best_score >= self.similarity_threshold and best_entry is not None:
            logger.info(
                "cache.similarity_hit",
                extra={
                    "session_id": session_id,
                    "similarity": round(best_score, 4),
                    "cached_query": best_entry.get("query", "")[:50],
                    "current_query": normalized_query[:50],
                },
            )
            return CacheHit(
                query=best_entry.get("query", normalized_query),
                response_text=best_entry.get("response_text", ""),
                similarity=best_score,
                route_type=best_entry.get("route_type", "smalltalk"),
                provider=best_entry.get("provider", "cache"),
                usage=best_entry.get("usage", {}),
            )

        logger.debug(
            "cache.similarity_miss",
            extra={
                "session_id": session_id,
                "best_score": round(best_score, 4),
                "threshold": self.similarity_threshold,
            },
        )
        return None

    # ------------------------------------------------------------------
    # 保存缓存
    # ------------------------------------------------------------------

    async def save_cache(
        self,
        session_id: str,
        normalized_query: str,
        response_text: str,
        *,
        user_id: str | None = None,
        route_type: str = "smalltalk",
        provider: str = "",
        usage: dict | None = None,
    ) -> None:
        """将 query + response + embedding 保存到缓存窗口。

        窗口使用 FIFO 策略，保留最近 window_size 条。
        """
        try:
            embed_provider = EmbeddingProviderFactory.create()
            result = await embed_provider.embed_documents([normalized_query])
            query_embedding = result.embeddings[0] if result.embeddings else None
        except Exception:
            logger.debug("cache.save_embedding_failed")
            query_embedding = None

        window_key = self._build_embeddings_key(session_id, user_id=user_id)
        existing = await get_json(window_key)
        entries: list[dict] = existing if isinstance(existing, list) else []

        settings = get_settings()
        entries.append({
            "query": normalized_query,
            "response_text": response_text,
            "embedding": query_embedding,
            "route_type": route_type,
            "provider": provider,
            "usage": usage or {},
        })

        # FIFO 裁剪
        window_size = settings.memory.window_size
        if len(entries) > window_size:
            entries = entries[-window_size:]

        await set_json(window_key, entries, ttl_seconds=settings.memory.window_ttl_seconds)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_embeddings_key(self, session_id: str, *, user_id: str | None = None) -> str:
        """构建 embedding 窗口缓存 key。"""
        settings = get_settings()
        suffix = f"{user_id}:{session_id}" if user_id else session_id
        return f"{settings.cache.prefix}:embeddings:{suffix}"

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量的 cosine similarity。"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ------------------------------------------------------------------
# 模块级单例
# ------------------------------------------------------------------

_service: WindowCacheService | None = None


def get_window_cache_service() -> WindowCacheService:
    global _service
    if _service is None:
        _service = WindowCacheService()
    return _service
