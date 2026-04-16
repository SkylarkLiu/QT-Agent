from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cache.redis_client import close_redis, ping_redis
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.init_db import initialize_database
from app.retrieval.milvus_store import initialize_milvus
from app.services.object_storage import initialize_minio


logger = get_logger("app.lifecycle")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    await initialize_database()
    await ping_redis()
    await initialize_minio()
    await initialize_milvus()
    logger.info(
        "application.startup",
        extra={"app_env": settings.app.env, "app_name": settings.app.name, "startup_retry_enabled": settings.startup_retry.enabled},
    )
    yield
    await close_redis()
    logger.info("application.shutdown", extra={"app_name": settings.app.name})
