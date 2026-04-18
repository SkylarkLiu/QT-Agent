from __future__ import annotations

from typing import Any

from app.skills.base import BaseSkill


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "执行联网搜索并整理结果。"
    route_types = ("websearch", "web_search")

    async def can_handle(self, state: dict[str, Any]) -> bool:
        route_mode = state.get("route_mode")
        if route_mode == "websearch":
            return True
        if state.get("selected_skill") == self.name:
            return True

        query = str(state.get("normalized_query") or state.get("user_message") or "").lower()
        return any(token in query for token in ("http", "网址", "新闻", "今天", "搜索", "web"))

    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        from app.graph.web_builder import build_web_search_subgraph

        graph = build_web_search_subgraph().compile()
        result = await graph.ainvoke(
            {
                **state,
                "selected_skill": self.name,
                "route_type": self.name,
            }
        )
        result["selected_skill"] = self.name
        result["route_type"] = result.get("route_type") or self.name
        return result
