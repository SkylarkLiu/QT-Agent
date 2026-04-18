from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

from app.skills.base import BaseSkill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: OrderedDict[str, BaseSkill] = OrderedDict()

    def register(self, skill: BaseSkill) -> BaseSkill:
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list(self) -> list[BaseSkill]:
        return list(self._skills.values())

    async def match(self, state: dict) -> BaseSkill | None:
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            if await skill.can_handle(state):
                return skill
        return None

    def extend(self, skills: Iterable[BaseSkill]) -> None:
        for skill in skills:
            self.register(skill)


_registry: SkillRegistry | None = None
_defaults_registered = False


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def register_default_skills() -> SkillRegistry:
    global _defaults_registered
    registry = get_skill_registry()
    if _defaults_registered:
        return registry

    from app.skills.knowledge_qa import KnowledgeQASkill
    from app.skills.mcp_tool import MCPToolSkill
    from app.skills.policy_compare import PolicyCompareSkill
    from app.skills.report_analysis import ReportAnalysisSkill
    from app.skills.web_search import WebSearchSkill

    registry.extend(
        [
            KnowledgeQASkill(),
            WebSearchSkill(),
            MCPToolSkill(),
            ReportAnalysisSkill(),
            PolicyCompareSkill(),
        ]
    )
    _defaults_registered = True
    return registry
