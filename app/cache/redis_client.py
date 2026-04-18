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
    try:
        await get_redis().ping()
    except Exception:
        logger.warning("redis.unavailable_startup", exc_info=True)
        raise
    logger.info("redis.connected")


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            logger.warning("redis.close_failed", exc_info=True)
    _redis = None


def build_window_cache_key(session_id: str, *, user_id: str | None = None) -> str:
    settings = get_settings()
    suffix = f"{user_id}:{session_id}" if user_id else session_id
    return f"{settings.cache.prefix}:window:{suffix}"


async def set_json(key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
    settings = get_settings()
    payload = json.dumps(value, ensure_ascii=False)
    try:
        await get_redis().set(key, payload, ex=ttl_seconds or settings.redis.ttl_seconds)
    except Exception:
        logger.warning("redis.set_failed", extra={"key": key[:120]}, exc_info=True)


async def get_json(key: str) -> Any | None:
    try:
        payload = await get_redis().get(key)
    except Exception:
        logger.warning("redis.get_failed", extra={"key": key[:120]}, exc_info=True)
        return None
    if payload is None:
        return None
    return json.loads(payload)


@asynccontextmanager
async def distributed_lock(name: str, *, timeout: int = 10) -> AsyncIterator[bool]:
    lock = None
    try:
        lock = get_redis().lock(name, timeout=timeout)
        acquired = await lock.acquire(blocking=False)
    except Exception:
        logger.warning("redis.lock_degraded", extra={"lock_name": name, "timeout": timeout}, exc_info=True)
        acquired = True
    try:
        yield acquired
    finally:
        if acquired and lock is not None:
            try:
                await lock.release()
            except Exception:
                logger.warning("redis.lock_release_failed", extra={"lock_name": name}, exc_info=True)
