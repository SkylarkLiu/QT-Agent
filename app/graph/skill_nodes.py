from __future__ import annotations

from app.skills.registry import get_skill_registry, register_default_skills


async def resolve_skill(state: dict) -> dict:
    registry = register_default_skills()
    selected_skill = state.get("selected_skill")
    if selected_skill and registry.get(selected_skill):
        return {
            "selected_skill": selected_skill,
            "available_skills": [skill.definition.model_dump() for skill in registry.list()],
        }

    matched = await registry.match(state)
    if matched is None:
        return {
            "selected_skill": None,
            "available_skills": [skill.definition.model_dump() for skill in registry.list()],
        }

    return {
        "selected_skill": matched.name,
        "available_skills": [skill.definition.model_dump() for skill in registry.list()],
        "route_type": "skill",
    }


def route_after_resolve_skill(state: dict) -> str:
    selected_skill = state.get("selected_skill")
    if not selected_skill:
        return "skill_unavailable"
    return selected_skill


def build_skill_executor(skill_name: str):
    async def execute_skill(state: dict) -> dict:
        registry = get_skill_registry()
        skill = registry.get(skill_name)
        if skill is None:
            return await skill_unavailable({**state, "selected_skill": skill_name})
        return await skill.invoke(state)

    return execute_skill


async def skill_unavailable(state: dict) -> dict:
    selected_skill = state.get("selected_skill") or "unknown"
    return {
        "selected_skill": selected_skill,
        "route_type": selected_skill,
        "response_text": f"当前没有可处理该请求的 skill：{selected_skill}。",
        "finish_reason": "no_skill",
        "usage": {},
        "stream_chunks": [],
    }
