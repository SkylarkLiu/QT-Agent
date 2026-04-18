from __future__ import annotations

from typing import Any

from app.skills.base import BaseSkill


class PolicyCompareSkill(BaseSkill):
    name = "policy_compare"
    description = "政策对比能力占位，后续可接入多文档比较分析。"
    route_types = ("policy_compare",)
    enabled = False

    async def can_handle(self, state: dict[str, Any]) -> bool:
        return state.get("selected_skill") == self.name

    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "selected_skill": self.name,
            "route_type": self.name,
            "response_text": "政策对比 skill 尚未启用。",
            "finish_reason": "placeholder",
            "usage": {},
            "stream_chunks": [],
        }
