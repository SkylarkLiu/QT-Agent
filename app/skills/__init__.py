"""Skills package."""

from app.skills.base import BaseSkill
from app.skills.mcp_tool import MCPToolSkill
from app.skills.registry import SkillRegistry, get_skill_registry, register_default_skills
from app.skills.schemas import SkillDefinition, SkillDispatchResult

__all__ = [
    "BaseSkill",
    "MCPToolSkill",
    "SkillDefinition",
    "SkillDispatchResult",
    "SkillRegistry",
    "get_skill_registry",
    "register_default_skills",
]
