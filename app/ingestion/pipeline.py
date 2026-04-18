"""Ingestion Pipeline — 完整的入库管道。

流程：
  upload API → IngestionService.ingest()
    1. 保存文件到 MinIO
    2. 记录 Document 元数据（status=pending）
    3. 调用 Pipeline.run():
       a. 根据 filename 选择 Parser
       b. 解析 → 得到 ParsedSection 列表
       c. Chunk → 得到 Chunk 列表
       d. 批量 Embedding
       e. 写入 Milvus
       f. 更新 Document.parser_status / chunk_count
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.chunker import Chunk, Chunker
from app.providers.parsers import get_parser
from app.retrieval.base import VectorDocument
from app.retrieval.milvus_store import get_milvus_store

logger = get_logger("app.ingestion.pipeline")

# 允许的最大文件大小检查
MAX_FILE_SIZE_MB = 50


class IngestionPipeline:
    """文档入库管道 — 串行执行 解析→切块→向量化→存储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chunker = Chunker()
        self.settings = get_settings()

    async def run(
        self,
        *,
        doc_id: str,
        kb_id: str,
        owner_user_id: str,
        filename: str,
        file_bytes: bytes,
        source_type: str,
    ) -> dict[str, Any]:
        """执行完整的入库管道。

        Returns:
            包含 chunk_count, parser_status, sections_count 等信息的 dict。
        """
        result: dict[str, Any] = {
            "doc_id": doc_id,
            "filename": filename,
            "parser_status": "processing",
            "chunk_count": 0,
            "sections_count": 0,
            "error": None,
        }

        try:
            # ─── Step 1: 解析 ────────────────────────────────
            parser = get_parser(filename)
            parse_result = await parser.parse(file_bytes)

            if parse_result.error:
                result["error"] = parse_result.error
                result["parser_status"] = "failed"
                return result

            result["sections_count"] = len(parse_result.sections)
            logger.info(
                "ingestion.parse_done",
                extra={
                    "doc_id": doc_id,
                    "source_type": parse_result.source_type,
                    "sections": len(parse_result.sections),
                    "pages": parse_result.total_pages,
                },
            )

            if not parse_result.sections:
                result["parser_status"] = "completed"
                result["error"] = "No content extracted from document"
                return result

            # ─── Step 2: 切块 ────────────────────────────────
            chunks: list[Chunk] = self.chunker.chunk_sections(
                parse_result.sections,
                doc_id=doc_id,
                kb_id=kb_id,
                owner_user_id=owner_user_id,
                source_type=parse_result.source_type,
            )
            result["chunk_count"] = len(chunks)
            logger.info(
                "ingestion.chunk_done",
                extra={"doc_id": doc_id, "chunks": len(chunks)},
            )

            if not chunks:
                result["parser_status"] = "completed"
                return result

            # ─── Step 3: 批量 Embedding ──────────────────────
            from app.providers.factories import EmbeddingProviderFactory

            embedding_provider = EmbeddingProviderFactory.create()
            batch_size = self.settings.ingestion.embedding_batch_size
            all_embeddings: list[list[float]] = []
            batch_tasks = []

            for offset in range(0, len(chunks), batch_size):
                batch = [c.content for c in chunks[offset : offset + batch_size]]
                batch_tasks.append(embedding_provider.embed_documents(batch))

            for emb_result in await asyncio.gather(*batch_tasks):
                all_embeddings.extend(emb_result.embeddings)

            logger.info(
                "ingestion.embedding_done",
                extra={"doc_id": doc_id, "total_embeddings": len(all_embeddings)},
            )

            # ─── Step 4: 写入 Milvus ────────────────────────
            vector_docs = [
                VectorDocument(
                    id=str(uuid.uuid4()),
                    content=chunk.content,
                    metadata=chunk.metadata,
                )
                for chunk in chunks
            ]
            milvus_store = get_milvus_store()
            await milvus_store.upsert(vector_docs, all_embeddings)

            logger.info(
                "ingestion.milvus_upsert_done",
                extra={"doc_id": doc_id, "vectors": len(vector_docs)},
            )

            result["parser_status"] = "completed"
            return result

        except Exception as exc:
            logger.exception(
                "ingestion.pipeline_error",
                extra={"doc_id": doc_id, "file_name": filename},
            )
            result["parser_status"] = "failed"
            result["error"] = str(exc)
            return result
