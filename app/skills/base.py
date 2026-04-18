from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.skills.schemas import SkillDefinition


class BaseSkill(ABC):
    name: str
    description: str
    route_types: tuple[str, ...] = ()
    enabled: bool = True

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name=self.name,
            description=self.description,
            route_types=list(self.route_types),
            enabled=self.enabled,
        )

    @abstractmethod
    async def can_handle(self, state: dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
