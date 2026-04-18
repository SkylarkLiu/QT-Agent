from __future__ import annotations

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    name: str
    description: str
    route_types: list[str] = Field(default_factory=list)
    enabled: bool = True


class SkillDispatchResult(BaseModel):
    selected_skill: str | None = None
    available_skills: list[SkillDefinition] = Field(default_factory=list)
