"""IngestionService — 文档上传 + 入库的业务编排层。"""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.pipeline import IngestionPipeline
from app.repositories.knowledge import DocumentRepository, KnowledgeBaseRepository
from app.services.object_storage import get_object_storage

logger = get_logger("app.services.ingestion")

# ─── source_type 映射 ─────────────────────────────────────

EXT_SOURCE_MAP: dict[str, str] = {
    ".txt": "text",
    ".md": "text",
    ".csv": "text",
    ".json": "text",
    ".xml": "text",
    ".html": "text",
    ".log": "text",
    ".yaml": "text",
    ".yml": "text",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tiff": "image",
}


def _detect_source_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return EXT_SOURCE_MAP.get(ext, "unknown")


def _content_type_for(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    ct_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return ct_map.get(ext, "application/octet-stream")


class IngestionService:
    """文档入库业务服务。

    职责：
    1. 校验文件类型/大小
    2. 上传 MinIO
    3. 创建 Document 记录
    4. 调用 Pipeline 执行解析→切块→向量化→存储
    5. 更新 Document 状态
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.settings = get_settings()

    def _validate_file(self, filename: str, file_size: int) -> str:
        """校验文件扩展名和大小，返回 source_type。"""
        ext = os.path.splitext(filename)[1].lower()
        allowed = self.settings.ingestion.allowed_extensions

        if ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(allowed)}",
            )

        max_bytes = self.settings.ingestion.max_file_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({file_size} bytes). Max: {max_bytes} bytes ({self.settings.ingestion.max_file_size_mb}MB).",
            )

        return _detect_source_type(filename)

    async def upload_and_ingest(
        self,
        *,
        knowledge_base_id: str,
        file: UploadFile,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """上传文件并触发入库管道。"""
        filename = file.filename or "unknown"
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # 1. 校验
        source_type = self._validate_file(filename, file_size)

        # 2. 校验知识库存在
        kb = await self.kb_repo.get(knowledge_base_id)
        if kb is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge base '{knowledge_base_id}' not found.",
            )

        # 3. 上传 MinIO
        object_name = f"documents/{knowledge_base_id}/{uuid.uuid4()}/{filename}"
        storage = get_object_storage()
        stored = await storage.upload_bytes(
            object_name,
            file_bytes,
            content_type=_content_type_for(filename),
        )
        storage_path = f"{stored.bucket}/{stored.object_name}"

        logger.info(
            "ingestion.upload_done",
            extra={
                "filename": filename,
                "size": file_size,
                "storage_path": storage_path,
            },
        )

        # 4. 创建 Document 记录
        doc = await self.doc_repo.create(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            storage_path=storage_path,
            source_type=source_type,
            file_size=file_size,
        )
        logger.info(
            "ingestion.document_created",
            extra={"doc_id": doc.id, "status": "pending"},
        )

        # 5. 执行入库管道（在后台异步执行）
        #    先更新状态为 processing
        await self.doc_repo.update_status(doc.id, parser_status="processing")
        await self.session.commit()

        # 6. 异步执行 pipeline
        owner_user_id = user_id or kb.user_id or ""

        # 使用 create_task 实现真正的异步后台执行
        import asyncio
        asyncio.create_task(
            self._run_pipeline(
                doc_id=doc.id,
                kb_id=knowledge_base_id,
                owner_user_id=owner_user_id,
                filename=filename,
                file_bytes=file_bytes,
                source_type=source_type,
            )
        )

        return {
            "document_id": doc.id,
            "filename": filename,
            "knowledge_base_id": knowledge_base_id,
            "parser_status": "processing",
            "message": "File uploaded. Ingestion pipeline started in background.",
        }

    async def _run_pipeline(
        self,
        *,
        doc_id: str,
        kb_id: str,
        owner_user_id: str,
        filename: str,
        file_bytes: bytes,
        source_type: str,
    ) -> None:
        """在独立协程中运行入库管道，确保异常不影响 API 响应。"""
        from app.db.session import get_sessionmaker

        try:
            async with get_sessionmaker()() as session:
                pipeline = IngestionPipeline(session)
                result = await pipeline.run(
                    doc_id=doc_id,
                    kb_id=kb_id,
                    owner_user_id=owner_user_id,
                    filename=filename,
                    file_bytes=file_bytes,
                    source_type=source_type,
                )

                # 更新 Document 记录
                doc_repo = DocumentRepository(session)
                await doc_repo.update_status(
                    doc_id,
                    parser_status=result["parser_status"],
                    chunk_count=result.get("chunk_count", 0),
                    error_message=result.get("error"),
                )
                await session.commit()

                logger.info(
                    "ingestion.pipeline_finished",
                    extra={
                        "doc_id": doc_id,
                        "status": result["parser_status"],
                        "chunks": result.get("chunk_count", 0),
                    },
                )

        except Exception as exc:
            logger.exception(
                "ingestion.pipeline_unhandled_error",
                extra={"doc_id": doc_id},
            )
            # 尝试更新为 failed
            try:
                async with get_sessionmaker()() as session:
                    doc_repo = DocumentRepository(session)
                    await doc_repo.update_status(
                        doc_id,
                        parser_status="failed",
                        error_message=str(exc),
                    )
                    await session.commit()
            except Exception:
                logger.exception("ingestion.status_update_failed", extra={"doc_id": doc_id})

    async def get_document_status(self, doc_id: str) -> dict[str, Any]:
        """查询文档入库状态。"""
        doc = await self.doc_repo.get(doc_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{doc_id}' not found.",
            )
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "parser_status": doc.parser_status,
            "chunk_count": doc.chunk_count,
            "error_message": doc.metadata_.get("error_message"),
            "metadata": doc.metadata_,
        }

    async def list_documents(
        self, kb_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """列出知识库下的所有文档。"""
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge base '{kb_id}' not found.",
            )

        docs = await self.doc_repo.list_by_kb(kb_id, limit=limit, offset=offset)
        total = await self.doc_repo.count_by_kb(kb_id)

        items = [
            {
                "id": d.id,
                "knowledge_base_id": d.knowledge_base_id,
                "filename": d.filename,
                "storage_path": d.storage_path,
                "source_type": d.metadata_.get("source_type", "unknown"),
                "parser_status": d.parser_status,
                "chunk_count": d.chunk_count,
                "file_size": d.metadata_.get("file_size", 0),
                "metadata": d.metadata_,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ]
        return items, total

    async def create_knowledge_base(
        self,
        *,
        name: str,
        user_id: str | None = None,
        description: str | None = None,
        visibility: str = "private",
    ) -> dict[str, Any]:
        """创建知识库。"""
        kb = await self.kb_repo.create(
            name=name,
            user_id=user_id,
            description=description,
            visibility=visibility,
        )
        await self.session.commit()
        return {
            "id": kb.id,
            "user_id": kb.user_id,
            "name": kb.name,
            "description": kb.description,
            "visibility": kb.visibility,
            "document_count": 0,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }

    async def list_knowledge_bases(
        self,
        user_id: str | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """列出知识库。"""
        kbs = await self.kb_repo.list_by_user(user_id, limit=limit, offset=offset)

        items = []
        for kb in kbs:
            doc_count = await self.kb_repo.count_documents(kb.id)
            items.append({
                "id": kb.id,
                "user_id": kb.user_id,
                "name": kb.name,
                "description": kb.description,
                "visibility": kb.visibility,
                "document_count": doc_count,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
                "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
            })

        return items, len(items)
