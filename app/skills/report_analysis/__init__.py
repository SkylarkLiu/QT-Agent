from __future__ import annotations

from typing import Any

from app.skills.base import BaseSkill


class ReportAnalysisSkill(BaseSkill):
    name = "report_analysis"
    description = "报表分析能力占位，后续可接入结构化分析与图表解释。"
    route_types = ("report_analysis",)
    enabled = False

    async def can_handle(self, state: dict[str, Any]) -> bool:
        return state.get("selected_skill") == self.name

    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "selected_skill": self.name,
            "route_type": self.name,
            "response_text": "报表分析 skill 尚未启用。",
            "finish_reason": "placeholder",
            "usage": {},
            "stream_chunks": [],
        }
