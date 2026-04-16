"""HistoryLoader — 会话历史恢复：先查 Redis 热窗口，未命中查 PostgreSQL 历史。

三层记忆架构：
  1. Redis 热窗口 — 最近 N 条消息，TTL 自动过期
  2. PostgreSQL 历史 — 全量持久化消息记录
  3. 摘要记忆 — 长历史压缩为 summary（P8-T4 实现）

职责：
  - load_history() 返回拼装后的完整历史
  - save_to_window() 将最新消息写入 Redis 热窗口
  - 供 load_session_context 节点调用
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.cache.redis_client import build_window_cache_key, get_json, set_json
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.provider import LLMMessage

logger = get_logger("app.memory.history")


@dataclass(slots=True)
class HistoryEntry:
    """单条历史消息。"""

    role: str
    content: str
    metadata: dict = field(default_factory=dict)

    def to_llm_message(self) -> LLMMessage:
        return LLMMessage(role=self.role, content=self.content)


class HistoryLoader:
    """会话历史加载器。

    策略：先从 Redis 热窗口读取，若 miss 则从 PostgreSQL 恢复并回填 Redis。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.window_size = settings.memory.window_size
        self.window_ttl = settings.memory.window_ttl_seconds

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def load_history(
        self,
        session_id: str,
        *,
        user_id: str | None = None,
        pg_messages: list[HistoryEntry] | None = None,
    ) -> list[LLMMessage]:
        """加载会话历史，返回 LLMMessage 列表。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID（用于构建缓存 key）
            pg_messages: PostgreSQL 中的历史消息（由调用方传入，避免重复查询）
        """
        # 1. 先查 Redis 热窗口
        window_entries = await self._load_from_redis(session_id, user_id=user_id)
        if window_entries is not None:
            logger.debug(
                "history.redis_hit",
                extra={"session_id": session_id, "count": len(window_entries)},
            )
            return [e.to_llm_message() for e in window_entries]

        # 2. Redis miss → 从 PostgreSQL 恢复
        if pg_messages is None:
            return []

        # 只保留最近 window_size 条
        recent = pg_messages[-self.window_size:] if len(pg_messages) > self.window_size else pg_messages

        # 3. 回填 Redis
        await self._save_to_redis(session_id, recent, user_id=user_id)
        logger.info(
            "history.pg_fallback",
            extra={"session_id": session_id, "pg_total": len(pg_messages), "window_size": len(recent)},
        )
        return [e.to_llm_message() for e in recent]

    async def save_to_window(
        self,
        session_id: str,
        entries: list[HistoryEntry],
        *,
        user_id: str | None = None,
    ) -> None:
        """将消息列表追加写入 Redis 热窗口。

        只保留最近 window_size 条（FIFO 淘汰）。
        """
        key = build_window_cache_key(session_id, user_id=user_id)

        # 读取现有窗口
        existing_raw = await get_json(key)
        existing: list[dict] = existing_raw if isinstance(existing_raw, list) else []

        # 追加新消息
        for entry in entries:
            existing.append({"role": entry.role, "content": entry.content, "metadata": entry.metadata})

        # FIFO 裁剪
        if len(existing) > self.window_size:
            existing = existing[-self.window_size :]

        await set_json(key, existing, ttl_seconds=self.window_ttl)
        logger.debug(
            "history.window_updated",
            extra={"session_id": session_id, "window_size": len(existing)},
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _load_from_redis(
        self, session_id: str, *, user_id: str | None = None
    ) -> list[HistoryEntry] | None:
        """从 Redis 热窗口加载。返回 None 表示 cache miss。"""
        key = build_window_cache_key(session_id, user_id=user_id)
        raw = await get_json(key)
        if raw is None or not isinstance(raw, list):
            return None

        entries: list[HistoryEntry] = []
        for item in raw:
            if isinstance(item, dict) and "role" in item and "content" in item:
                entries.append(
                    HistoryEntry(
                        role=item["role"],
                        content=item["content"],
                        metadata=item.get("metadata", {}),
                    )
                )
        return entries if entries else None

    async def _save_to_redis(
        self,
        session_id: str,
        entries: list[HistoryEntry],
        *,
        user_id: str | None = None,
    ) -> None:
        """将历史写入 Redis 热窗口。"""
        key = build_window_cache_key(session_id, user_id=user_id)
        data = [{"role": e.role, "content": e.content, "metadata": e.metadata} for e in entries]
        await set_json(key, data, ttl_seconds=self.window_ttl)


# ------------------------------------------------------------------
# 模块级单例
# ------------------------------------------------------------------

_loader: HistoryLoader | None = None


def get_history_loader() -> HistoryLoader:
    global _loader
    if _loader is None:
        _loader = HistoryLoader()
    return _loader
