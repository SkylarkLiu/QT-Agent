from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str | None = None
    username: str
    session_id: str | None = None
    message: str = Field(min_length=1)
    model: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: str
    user_id: str | None = None
    model: str
    content: str
    provider: str
    route_type: str | None = None
    cache_hit: bool = False
    finish_reason: str | None = None
    usage: dict = Field(default_factory=dict)


class ChatHistoryQuery(BaseModel):
    session_id: str
    limit: int = Field(default=50, ge=1, le=200)


class ChatMessageItem(BaseModel):
    id: str
    session_id: str
    user_id: str | None = None
    role: str
    content: str
    model: str | None = None
    metadata: dict = Field(default_factory=dict)
    token_usage: dict = Field(default_factory=dict)
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: str
    items: list[ChatMessageItem]
