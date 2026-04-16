from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

from minio import Minio

from app.core.config import get_settings
from app.core.logging import get_logger


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
        exists = await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        if not exists:
            await asyncio.to_thread(self.client.make_bucket, self.bucket)
        logger.info("minio.bucket_ready", extra={"service_name": self.bucket})

    async def upload_bytes(self, object_name: str, content: bytes, content_type: str = "application/octet-stream") -> StoredObject:
        data_stream = io.BytesIO(content)
        result = await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            data_stream,
            len(content),
            content_type=content_type,
        )
        return StoredObject(bucket=self.bucket, object_name=object_name, etag=result.etag)

    async def download_bytes(self, object_name: str) -> bytes:
        response = await asyncio.to_thread(self.client.get_object, self.bucket, object_name)
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


async def initialize_minio() -> None:
    await get_object_storage().ensure_bucket()
