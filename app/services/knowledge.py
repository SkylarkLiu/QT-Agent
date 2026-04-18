from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge import DocumentRepository, KnowledgeBaseRepository
from app.retrieval import RetrievalAccessScope
from app.retrieval.retriever import get_retriever
from app.schemas.knowledge import (
    KnowledgeSearchDebugItem,
    KnowledgeSearchDebugRequest,
    KnowledgeSearchDebugResponse,
    RetrievalAccessScopePayload,
)


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.doc_repo = DocumentRepository(session)

    async def ensure_kb_access(self, kb_id: str, *, user_id: str | None) -> Any:
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
        if kb.user_id is not None and kb.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The current user cannot access this knowledge base.",
            )
        return kb

    async def ensure_document_access(self, doc_id: str, *, user_id: str | None) -> tuple[Any, Any]:
        result = await self.doc_repo.get_with_knowledge_base(doc_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        document, kb = result
        if kb.user_id is not None and kb.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The current user cannot access this document.",
            )
        return document, kb

    async def get_document_detail(self, doc_id: str, *, user_id: str | None) -> dict[str, Any]:
        doc, _kb = await self.ensure_document_access(doc_id, user_id=user_id)
        return {
            "id": doc.id,
            "knowledge_base_id": doc.knowledge_base_id,
            "filename": doc.filename,
            "storage_path": doc.storage_path,
            "source_type": doc.metadata_.get("source_type", "unknown"),
            "parser_status": doc.parser_status,
            "chunk_count": doc.chunk_count,
            "file_size": doc.metadata_.get("file_size", 0),
            "metadata": doc.metadata_,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }

    async def search_debug(
        self,
        kb_id: str,
        payload: KnowledgeSearchDebugRequest,
    ) -> KnowledgeSearchDebugResponse:
        await self.ensure_kb_access(kb_id, user_id=payload.user_id)
        access_scope = RetrievalAccessScope(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            accessible_kb_ids=payload.accessible_kb_ids or [kb_id],
        )
        if kb_id not in access_scope.accessible_kb_ids:
            access_scope.accessible_kb_ids.append(kb_id)

        retriever = get_retriever()
        docs = await retriever.retrieve(
            payload.query,
            top_k=payload.top_k,
            access_scope=access_scope,
        )
        hits = [
            KnowledgeSearchDebugItem(
                id=doc.id,
                content=doc.content,
                score=doc.score,
                metadata=doc.metadata,
            )
            for doc in docs
        ]
        return KnowledgeSearchDebugResponse(
            query=payload.query,
            top_k=payload.top_k,
            knowledge_base_id=kb_id,
            access_scope=RetrievalAccessScopePayload(
                user_id=access_scope.user_id,
                tenant_id=access_scope.tenant_id,
                accessible_kb_ids=access_scope.accessible_kb_ids,
            ),
            applied_filter=access_scope.to_metadata_filter(),
            hits=hits,
        )
