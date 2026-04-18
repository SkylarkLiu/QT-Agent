from __future__ import annotations

from typing import Any

from app.mcp.tool_adapter import MCPToolAdapter
from app.skills.base import BaseSkill


class MCPToolSkill(BaseSkill):
    name = "mcp_tool"
    description = "通过 MCP bridge 调用工具能力。"
    route_types = ("mcp_call", "tool")

    async def can_handle(self, state: dict[str, Any]) -> bool:
        route_mode = state.get("route_mode")
        if route_mode == "tool":
            return True
        if state.get("selected_skill") == self.name:
            return True

        query = str(state.get("normalized_query") or state.get("user_message") or "").lower()
        return any(token in query for token in ("mcp", "tool", "工具", "关键词", "求和", "sum", "session"))

    async def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        adapter = MCPToolAdapter()
        result = await adapter.execute(
            {
                **state,
                "selected_skill": self.name,
            }
        )
        result["selected_skill"] = self.name
        return result
