"""Knowledge base & document repositories."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, kb_id: str) -> KnowledgeBase | None:
        return await self.session.get(KnowledgeBase, kb_id)

    async def get_accessible(self, kb_id: str, *, user_id: str | None) -> KnowledgeBase | None:
        kb = await self.get(kb_id)
        if kb is None:
            return None
        if kb.user_id is None:
            return kb
        if user_id is None or kb.user_id != user_id:
            return None
        return kb

    async def list_by_user(self, user_id: str | None, *, limit: int = 50, offset: int = 0) -> Sequence[KnowledgeBase]:
        stmt: Select[tuple[KnowledgeBase]] = select(KnowledgeBase)
        if user_id:
            stmt = stmt.where(KnowledgeBase.user_id == user_id)
        else:
            stmt = stmt.where(KnowledgeBase.user_id.is_(None))
        stmt = stmt.order_by(KnowledgeBase.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.scalars(stmt)
        return result.all()

    async def create(
        self,
        *,
        name: str,
        user_id: str | None = None,
        description: str | None = None,
        visibility: str = "private",
    ) -> KnowledgeBase:
        kb = KnowledgeBase(
            name=name,
            user_id=user_id,
            description=description,
            visibility=visibility,
        )
        self.session.add(kb)
        await self.session.flush()
        return kb

    async def count_documents(self, kb_id: str) -> int:
        stmt = select(func.count()).where(Document.knowledge_base_id == kb_id)
        result = await self.session.scalar(stmt)
        return result or 0


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, doc_id: str) -> Document | None:
        return await self.session.get(Document, doc_id)

    async def get_with_knowledge_base(self, doc_id: str) -> tuple[Document, KnowledgeBase] | None:
        stmt = (
            select(Document, KnowledgeBase)
            .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
            .where(Document.id == doc_id)
        )
        row = await self.session.execute(stmt)
        result = row.first()
        if result is None:
            return None
        return result[0], result[1]

    async def list_by_kb(
        self, kb_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Document]:
        stmt: Select[tuple[Document]] = (
            select(Document)
            .where(Document.knowledge_base_id == kb_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return result.all()

    async def create(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        storage_path: str,
        source_type: str = "unknown",
        file_size: int = 0,
        metadata: dict | None = None,
    ) -> Document:
        doc = Document(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            storage_path=storage_path,
            parser_status="pending",
            chunk_count=0,
            metadata_=metadata or {},
        )
        # 在 metadata JSON 中记录 source_type 和 file_size
        doc.metadata_["source_type"] = source_type
        doc.metadata_["file_size"] = file_size
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def update_status(
        self,
        doc_id: str,
        *,
        parser_status: str | None = None,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        doc = await self.get(doc_id)
        if doc is None:
            return None
        if parser_status is not None:
            doc.parser_status = parser_status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if error_message is not None:
            doc.metadata_["error_message"] = error_message
        await self.session.flush()
        return doc

    async def count_by_kb(self, kb_id: str) -> int:
        stmt = select(func.count()).where(Document.knowledge_base_id == kb_id)
        result = await self.session.scalar(stmt)
        return result or 0
