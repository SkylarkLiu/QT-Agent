from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


RouteMode = Literal["auto", "knowledge", "websearch", "tool"]
TimelineStatus = Literal["completed", "running", "pending"]


def _validate_uuid(v: str, field_name: str = "session_id") -> str:
    """校验字符串是否为合法 UUID，否则抛出 ValueError。"""
    try:
        UUID(v)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} 必须是合法的 UUID 格式（如 550e8400-e29b-41d4-a716-446655440000）")
    return v


class ChatRequest(BaseModel):
    user_id: str | None = None
    username: str
    session_id: str | None = None
    message: str = Field(min_length=1)
    model: str | None = None
    route_mode: RouteMode = "auto"
    stream: bool = False

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_uuid(v)
        return v


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

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        return _validate_uuid(v)

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


class DebugRecallItem(BaseModel):
    id: str
    title: str
    source: str
    score: float = 0.0
    snippet: str


class DebugToolCall(BaseModel):
    id: str
    name: str
    target: str
    status: TimelineStatus
    latency_ms: int = 0


class DebugTimelineItem(BaseModel):
    id: str
    label: str
    status: TimelineStatus
    timestamp: str
    detail: str


class ChatDebugResponse(BaseModel):
    session_id: str
    user_id: str | None = None
    graph_state: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    recall_items: list[DebugRecallItem] = Field(default_factory=list)
    cache_info: dict = Field(default_factory=dict)
    tool_calls: list[DebugToolCall] = Field(default_factory=list)
    api_response: dict = Field(default_factory=dict)
    rendered_payload: dict = Field(default_factory=dict)
    timeline: list[DebugTimelineItem] = Field(default_factory=list)
