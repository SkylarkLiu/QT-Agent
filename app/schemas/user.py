from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    user_id: str | None = None
    username: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str | None
    email: str | None
    is_active: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
