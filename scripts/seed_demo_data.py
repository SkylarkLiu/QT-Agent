from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.init_db import initialize_database
from app.db.models import Document, KnowledgeBase, Session as ChatSession, User
from app.db.session import close_engine, get_sessionmaker
from app.ingestion.pipeline import IngestionPipeline
from app.repositories.chat import MessageRepository, SessionRepository, UserRepository
from app.repositories.knowledge import DocumentRepository, KnowledgeBaseRepository
from app.retrieval.milvus_store import initialize_milvus
from app.services.object_storage import get_object_storage


logger = get_logger("scripts.seed_demo_data")
BASE_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = BASE_DIR / "test_data"
DEMO_FILES = [
    "qt_agent_development_guide.md",
    "gree_company_intro.md",
    "gree_technology.md",
]


def _content_type_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    return mapping.get(ext, "application/octet-stream")


def _source_type_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}:
        return "image"
    return "text"


async def ensure_user(
    username: str,
    *,
    display_name: str,
    email: str,
    metadata: dict[str, Any],
) -> User:
    async with get_sessionmaker()() as session:
        repo = UserRepository(session)
        current = await repo.get_by_username(username)
        if current is None:
            current = await repo.create(
                username=username,
                display_name=display_name,
                email=email,
                metadata=metadata,
            )
            await session.commit()
            logger.info("scripts.seed_demo_data.user_created", extra={"user_id": current.id, "username": username})
        else:
            updated = False
            if current.display_name != display_name:
                current.display_name = display_name
                updated = True
            if current.email != email:
                current.email = email
                updated = True
            if current.metadata_ != metadata:
                current.metadata_ = metadata
                updated = True
            if updated:
                await session.commit()
                logger.info("scripts.seed_demo_data.user_updated", extra={"user_id": current.id, "username": username})
        await session.refresh(current)
        return current


async def ensure_knowledge_base(*, user_id: str, name: str, description: str) -> KnowledgeBase:
    async with get_sessionmaker()() as session:
        stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id, KnowledgeBase.name == name)
        current = await session.scalar(stmt)
        if current is None:
            repo = KnowledgeBaseRepository(session)
            current = await repo.create(
                name=name,
                user_id=user_id,
                description=description,
                visibility="private",
            )
            current.metadata_ = {"seeded": True}
            await session.commit()
            logger.info(
                "scripts.seed_demo_data.knowledge_base_created",
                extra={"knowledge_base_id": current.id, "user_id": user_id, "name": name},
            )
        await session.refresh(current)
        return current


async def ensure_document_seed(
    *,
    knowledge_base_id: str,
    owner_user_id: str,
    filename: str,
) -> dict[str, Any]:
    path = TEST_DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Demo file not found: {path}")

    file_bytes = path.read_bytes()
    storage = get_object_storage()
    object_name = f"seed/{knowledge_base_id}/{filename}"
    stored = await storage.upload_bytes(
        object_name,
        file_bytes,
        content_type=_content_type_for(filename),
    )
    storage_path = f"{stored.bucket}/{stored.object_name}"

    async with get_sessionmaker()() as session:
        stmt = select(Document).where(Document.knowledge_base_id == knowledge_base_id, Document.filename == filename)
        doc = await session.scalar(stmt)
        doc_repo = DocumentRepository(session)

        if doc is None:
            doc = await doc_repo.create(
                knowledge_base_id=knowledge_base_id,
                filename=filename,
                storage_path=storage_path,
                source_type=_source_type_for(filename),
                file_size=len(file_bytes),
                metadata={"seeded": True},
            )
        else:
            doc.storage_path = storage_path
            doc.parser_status = "processing"
            doc.chunk_count = 0
            doc.metadata_["seeded"] = True
            doc.metadata_["source_type"] = _source_type_for(filename)
            doc.metadata_["file_size"] = len(file_bytes)

        await session.commit()

        pipeline = IngestionPipeline(session)
        result = await pipeline.run(
            doc_id=doc.id,
            kb_id=knowledge_base_id,
            owner_user_id=owner_user_id,
            filename=filename,
            file_bytes=file_bytes,
            source_type=_source_type_for(filename),
        )
        await doc_repo.update_status(
            doc.id,
            parser_status=result["parser_status"],
            chunk_count=result.get("chunk_count", 0),
            error_message=result.get("error"),
        )
        await session.commit()
        await session.refresh(doc)

        logger.info(
            "scripts.seed_demo_data.document_seeded",
            extra={
                "document_id": doc.id,
                "knowledge_base_id": knowledge_base_id,
                "filename": filename,
                "parser_status": doc.parser_status,
                "chunk_count": doc.chunk_count,
            },
        )
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "parser_status": doc.parser_status,
            "chunk_count": doc.chunk_count,
        }


async def ensure_demo_session(*, user_id: str) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        session_repo = SessionRepository(session)
        message_repo = MessageRepository(session)

        stmt = select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.title == "P14 Demo Session")
        current = await session.scalar(stmt)
        if current is None:
            current = await session_repo.get_or_create(
                session_id=None,
                user_id=user_id,
                title="P14 Demo Session",
            )
            await message_repo.create(
                session_id=current.id,
                user_id=user_id,
                role="user",
                content="请总结一下 QT-Agent 这个项目适合做什么。",
                metadata={"seeded": True},
            )
            await message_repo.create(
                session_id=current.id,
                user_id=user_id,
                role="assistant",
                content="QT-Agent 适合用于企业知识问答、调试智能体流程、联调 RAG 与 MCP 工具链。",
                model="mock-echo",
                metadata={"seeded": True, "route_type": "knowledge_qa"},
            )
            await session.commit()
            logger.info("scripts.seed_demo_data.session_created", extra={"session_id": current.id, "user_id": user_id})

        return {"session_id": current.id, "title": current.title}


async def main() -> None:
    if not TEST_DATA_DIR.exists():
        raise FileNotFoundError(f"Test data directory not found: {TEST_DATA_DIR}")

    logger.info("scripts.seed_demo_data.start")
    await initialize_database()
    await get_object_storage().ensure_bucket()
    await initialize_milvus()

    demo_user = await ensure_user(
        "demo_user",
        display_name="Demo User",
        email="demo_user@example.com",
        metadata={"seeded": True, "role": "demo"},
    )
    ops_user = await ensure_user(
        "ops_user",
        display_name="Ops User",
        email="ops_user@example.com",
        metadata={"seeded": True, "role": "ops"},
    )

    demo_kb = await ensure_knowledge_base(
        user_id=demo_user.id,
        name="产品与研发资料库",
        description="用于发布验证和调试演示的默认知识库。",
    )
    ops_kb = await ensure_knowledge_base(
        user_id=ops_user.id,
        name="运维与发布资料库",
        description="用于演示多用户知识隔离和发布运维资料。",
    )

    documents = []
    for filename in DEMO_FILES[:2]:
        documents.append(await ensure_document_seed(
            knowledge_base_id=demo_kb.id,
            owner_user_id=demo_user.id,
            filename=filename,
        ))
    documents.append(await ensure_document_seed(
        knowledge_base_id=ops_kb.id,
        owner_user_id=ops_user.id,
        filename=DEMO_FILES[2],
    ))

    demo_session = await ensure_demo_session(user_id=demo_user.id)

    summary = {
        "users": [
            {"id": demo_user.id, "username": demo_user.username},
            {"id": ops_user.id, "username": ops_user.username},
        ],
        "knowledge_bases": [
            {"id": demo_kb.id, "name": demo_kb.name, "user_id": demo_kb.user_id},
            {"id": ops_kb.id, "name": ops_kb.name, "user_id": ops_kb.user_id},
        ],
        "documents": documents,
        "session": demo_session,
        "test_data_dir": os.fspath(TEST_DATA_DIR),
    }
    logger.info("scripts.seed_demo_data.done", extra={"seed_summary": summary})
    print(summary)
    await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
