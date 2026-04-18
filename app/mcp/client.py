from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPToolResult:
    tool_name: str
    status: str
    content: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseMCPClient(ABC):
    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        raise NotImplementedError


class MockMCPClient(BaseMCPClient):
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        payload = arguments or {}
        state = context or {}

        if tool_name == "debug.echo":
            message = str(payload.get("message") or state.get("user_message") or "")
            return MCPToolResult(
                tool_name=tool_name,
                status="completed",
                content=f"MCP echo: {message}",
                payload={
                    "echo": message,
                    "session_id": state.get("session_id"),
                    "user_id": state.get("user_id"),
                },
            )

        if tool_name == "debug.session_context":
            summary = {
                "session_id": state.get("session_id"),
                "user_id": state.get("user_id"),
                "route_mode": state.get("route_mode", "auto"),
                "selected_skill": state.get("selected_skill"),
                "history_count": len(state.get("history_messages", [])),
            }
            return MCPToolResult(
                tool_name=tool_name,
                status="completed",
                content="已返回当前会话上下文快照。",
                payload=summary,
            )

        if tool_name == "utility.keyword_extract":
            text = str(payload.get("text") or state.get("user_message") or "")
            keywords = [token for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", text)[:8]]
            return MCPToolResult(
                tool_name=tool_name,
                status="completed",
                content=f"共提取 {len(keywords)} 个关键词。",
                payload={"keywords": keywords},
            )

        if tool_name == "utility.sum_numbers":
            numbers = payload.get("numbers") or []
            numeric_values = [float(item) for item in numbers]
            total = sum(numeric_values)
            return MCPToolResult(
                tool_name=tool_name,
                status="completed",
                content=f"数字求和结果为 {total:g}。",
                payload={"numbers": numeric_values, "total": total},
            )

        return MCPToolResult(
            tool_name=tool_name,
            status="not_found",
            content=f"未找到 MCP 工具：{tool_name}",
            payload={"available": []},
        )
