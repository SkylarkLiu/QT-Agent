from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

from minio import Minio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.runtime import run_with_timeout


logger = get_logger("app.storage.minio")
_client: "ObjectStorageClient | None" = None


@dataclass(slots=True)
class StoredObject:
    bucket: str
    object_name: str
    etag: str | None = None


class ObjectStorageClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.bucket = settings.minio.bucket
        self.client = Minio(
            endpoint=settings.minio.endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            secure=settings.minio.secure,
        )

    async def ensure_bucket(self) -> None:
        timeout = self.settings.runtime.object_storage_timeout_seconds
        exists = await run_with_timeout(
            lambda: asyncio.to_thread(self.client.bucket_exists, self.bucket),
            timeout_seconds=timeout,
            timeout_message=f"MinIO bucket_exists timed out for '{self.bucket}'.",
        )
        if not exists:
            await run_with_timeout(
                lambda: asyncio.to_thread(self.client.make_bucket, self.bucket),
                timeout_seconds=timeout,
                timeout_message=f"MinIO make_bucket timed out for '{self.bucket}'.",
            )
        logger.info("minio.bucket_ready", extra={"service_name": self.bucket})

    async def upload_bytes(self, object_name: str, content: bytes, content_type: str = "application/octet-stream") -> StoredObject:
        data_stream = io.BytesIO(content)
        timeout = self.settings.runtime.object_storage_timeout_seconds
        result = await run_with_timeout(
            lambda: asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                object_name,
                data_stream,
                len(content),
                content_type=content_type,
            ),
            timeout_seconds=timeout,
            timeout_message=f"MinIO upload timed out for '{object_name}'.",
        )
        return StoredObject(bucket=self.bucket, object_name=object_name, etag=result.etag)

    async def download_bytes(self, object_name: str) -> bytes:
        timeout = self.settings.runtime.object_storage_timeout_seconds
        response = await run_with_timeout(
            lambda: asyncio.to_thread(self.client.get_object, self.bucket, object_name),
            timeout_seconds=timeout,
            timeout_message=f"MinIO download timed out for '{object_name}'.",
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def get_object_storage() -> ObjectStorageClient:
    global _client
    if _client is None:
        _client = ObjectStorageClient()
    return _client


async def initialize_minio() -> bool:
    try:
        await get_object_storage().ensure_bucket()
    except Exception:
        logger.warning("minio.unavailable_startup", exc_info=True)
        return False
    return True
