from __future__ import annotations

from typing import Any

from app.skills.base import BaseSkill


class KnowledgeQASkill(BaseSkill):
    name = "knowledge_qa"
    description = "基于知识库召回结果进行问答。"
    route_types = ("knowledge", "knowledge_qa")

    async def can_handle(self, state: dict[str, Any]) -> bool:
        route_mode = state.get("route_mode")
        if route_mode == "knowledge":
            return True
        if state.get("selected_skill") == self.name:
            return True

        query = str(state.get("normalized_query") or state.get("user_message") or "").lower()
        return any(token in query for token in ("知识库", "文档", "kb", "rag", "资料"))

    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        from app.graph.rag_builder import build_rag_subgraph

        graph = build_rag_subgraph().compile()
        result = await graph.ainvoke(
            {
                **state,
                "selected_skill": self.name,
                "route_type": self.name,
            }
        )
        if result.get("need_web_fallback"):
            result["selected_skill"] = "web_search"
            result["route_type"] = "skill"
        else:
            result["selected_skill"] = self.name
            result["route_type"] = result.get("route_type") or self.name
        return result
