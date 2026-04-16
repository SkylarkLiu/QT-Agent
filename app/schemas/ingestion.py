"""Ingestion schemas — 文档上传、入库状态、知识库管理。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── 知识库 ───────────────────────────────────────────────


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    visibility: Literal["private", "public"] = "private"


class KnowledgeBaseResponse(BaseModel):
    id: str
    user_id: str | None
    name: str
    description: str | None
    visibility: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    total: int


# ─── 文档上传 ─────────────────────────────────────────────


class UploadDocumentRequest(BaseModel):
    """上传文档请求（Form + File 由路由层处理，此 schema 用于 body 参数）。"""

    knowledge_base_id: str = Field(description="目标知识库 ID")


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    storage_path: str
    source_type: str = "unknown"
    parser_status: str
    chunk_count: int
    file_size: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class UploadDocumentResponse(BaseModel):
    document_id: str
    filename: str
    knowledge_base_id: str
    parser_status: str
    message: str


# ─── 入库状态 ─────────────────────────────────────────────


class IngestionStatusResponse(BaseModel):
    document_id: str
    filename: str
    parser_status: Literal["pending", "processing", "completed", "failed"]
    chunk_count: int
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
