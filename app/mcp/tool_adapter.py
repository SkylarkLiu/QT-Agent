from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from app.mcp.client import BaseMCPClient, MockMCPClient
from app.mcp.registry import MCPToolDefinition, register_default_mcp_tools


class BaseToolAdapter(ABC):
    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MCPToolAdapter(BaseToolAdapter):
    def __init__(self, client: BaseMCPClient | None = None) -> None:
        self.client = client or MockMCPClient()
        self.registry = register_default_mcp_tools()

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        tool = self._resolve_tool(state)
        arguments = self._build_arguments(tool, state)
        result = await self.client.call_tool(tool.name, arguments, context=state)

        return {
            "route_type": "mcp_call",
            "selected_skill": state.get("selected_skill") or "mcp_tool",
            "provider_name": "mcp",
            "finish_reason": "tool_completed" if result.status == "completed" else result.status,
            "response_text": result.content,
            "usage": {},
            "stream_chunks": [],
            "mcp_tool_name": tool.name,
            "mcp_arguments": arguments,
            "mcp_tool_result": {
                "status": result.status,
                "content": result.content,
                "payload": result.payload,
                "metadata": result.metadata,
            },
            "available_mcp_tools": [
                {
                    "name": item.name,
                    "description": item.description,
                    "tags": list(item.tags),
                    "enabled": item.enabled,
                }
                for item in self.registry.list()
            ],
        }

    def _resolve_tool(self, state: dict[str, Any]) -> MCPToolDefinition:
        requested_tool = state.get("mcp_tool_name")
        if requested_tool:
            tool = self.registry.get(str(requested_tool))
            if tool is not None:
                return tool

        query = str(state.get("normalized_query") or state.get("user_message") or "")
        matched = self.registry.match(query)
        if matched is not None:
            return matched

        return self.registry.get("debug.echo") or self.registry.list()[0]

    def _build_arguments(self, tool: MCPToolDefinition, state: dict[str, Any]) -> dict[str, Any]:
        message = str(state.get("user_message") or "")
        if tool.name == "debug.session_context":
            return {}
        if tool.name == "utility.keyword_extract":
            return {"text": message}
        if tool.name == "utility.sum_numbers":
            numbers = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", message)]
            return {"numbers": numbers}
        return {"message": message}
