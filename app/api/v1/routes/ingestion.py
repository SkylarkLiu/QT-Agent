"""Ingestion API — 知识库管理、文档上传、入库状态查询。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.ingestion import (
    CreateKnowledgeBaseRequest,
    DocumentListResponse,
    DocumentResponse,
    IngestionStatusResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    UploadDocumentResponse,
)
from app.services.ingestion import IngestionService

router = APIRouter()


# ─── 知识库管理 ──────────────────────────────────────────


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, summary="创建知识库")
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    user_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = IngestionService(session)
    return await service.create_knowledge_base(
        name=body.name,
        user_id=user_id,
        description=body.description,
        visibility=body.visibility,
    )


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse, summary="列出知识库")
async def list_knowledge_bases(
    user_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = IngestionService(session)
    items, total = await service.list_knowledge_bases(user_id, limit=limit, offset=offset)
    return {"items": items, "total": total}


# ─── 文档上传与入库 ──────────────────────────────────────


@router.post(
    "/ingest/upload",
    response_model=UploadDocumentResponse,
    summary="上传文档并触发入库",
)
async def upload_document(
    knowledge_base_id: str = Form(..., description="目标知识库 ID"),
    file: UploadFile = File(..., description="要上传的文件"),
    user_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = IngestionService(session)
    return await service.upload_and_ingest(
        knowledge_base_id=knowledge_base_id,
        file=file,
        user_id=user_id,
    )


@router.get(
    "/documents/{doc_id}/status",
    response_model=IngestionStatusResponse,
    summary="查询文档入库状态",
)
async def get_document_status(
    doc_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = IngestionService(session)
    return await service.get_document_status(doc_id)


@router.get(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentListResponse,
    summary="列出知识库下的文档",
)
async def list_documents(
    kb_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = IngestionService(session)
    items, total = await service.list_documents(kb_id, limit=limit, offset=offset)
    return {"items": items, "total": total}
