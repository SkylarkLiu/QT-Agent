from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalAccessScopePayload(BaseModel):
    user_id: str | None = None
    tenant_id: str | None = None
    accessible_kb_ids: list[str] = Field(default_factory=list)


class KnowledgeSearchDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    user_id: str | None = None
    tenant_id: str | None = None
    accessible_kb_ids: list[str] = Field(default_factory=list)


class KnowledgeSearchDebugItem(BaseModel):
    id: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchDebugResponse(BaseModel):
    query: str
    top_k: int
    knowledge_base_id: str
    access_scope: RetrievalAccessScopePayload
    applied_filter: dict[str, Any] = Field(default_factory=dict)
    hits: list[KnowledgeSearchDebugItem] = Field(default_factory=list)
