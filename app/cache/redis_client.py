from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger("app.cache.redis")
_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis.url, decode_responses=True)
    return _redis


async def ping_redis() -> None:
    await get_redis().ping()
    logger.info("redis.connected")


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def build_window_cache_key(session_id: str, *, user_id: str | None = None) -> str:
    settings = get_settings()
    suffix = f"{user_id}:{session_id}" if user_id else session_id
    return f"{settings.cache.prefix}:window:{suffix}"


async def set_json(key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
    settings = get_settings()
    payload = json.dumps(value, ensure_ascii=False)
    await get_redis().set(key, payload, ex=ttl_seconds or settings.redis.ttl_seconds)


async def get_json(key: str) -> Any | None:
    payload = await get_redis().get(key)
    if payload is None:
        return None
    return json.loads(payload)


@asynccontextmanager
async def distributed_lock(name: str, *, timeout: int = 10) -> AsyncIterator[bool]:
    lock = get_redis().lock(name, timeout=timeout)
    acquired = await lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
