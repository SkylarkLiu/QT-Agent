"""Memory package — 上下文管理与记忆模块。

三层记忆架构：
  Layer 1: 摘要 (Summary) — 早期历史 LLM 压缩
  Layer 2: 近期窗口 (Recent Window) — 最近 N 条原始消息
  Layer 3: 热缓存 (Hot Cache) — Redis 热窗口缓存
"""

from app.memory.checkpointer import PostgresCheckpointer
from app.memory.history_loader import HistoryEntry, HistoryLoader, get_history_loader
from app.memory.summary_memory import MemoryLayers, SummaryMemoryService, get_summary_memory_service
from app.memory.window_cache import CacheHit, WindowCacheService, get_window_cache_service

__all__ = [
    "CacheHit",
    "HistoryEntry",
    "HistoryLoader",
    "MemoryLayers",
    "PostgresCheckpointer",
    "SummaryMemoryService",
    "WindowCacheService",
    "get_history_loader",
    "get_summary_memory_service",
    "get_window_cache_service",
]

