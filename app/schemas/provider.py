from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from typing import Literal, TypedDict

class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class MessageDict(TypedDict):

    role: Literal["system", "user", "assistant", "tool"]

    content: str

class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMStreamChunk(BaseModel):
    delta: str = ""
    model: str
    provider: str
    index: int = 0
    finish_reason: str | None = None
    done: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class EmbeddingResult(BaseModel):
    provider: str
    model: str
    embeddings: list[list[float]]
    dimensions: int
    raw: dict[str, Any] = Field(default_factory=dict)
