from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPToolDefinition:
    name: str
    description: str
    tags: tuple[str, ...] = ()
    input_schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def matches(self, query: str) -> bool:
        normalized = query.lower()
        return any(tag.lower() in normalized for tag in self.tags)


class MCPRegistry:
    def __init__(self) -> None:
        self._tools: OrderedDict[str, MCPToolDefinition] = OrderedDict()

    def register(self, tool: MCPToolDefinition) -> MCPToolDefinition:
        self._tools[tool.name] = tool
        return tool

    def extend(self, tools: Iterable[MCPToolDefinition]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> MCPToolDefinition | None:
        return self._tools.get(name)

    def list(self) -> list[MCPToolDefinition]:
        return list(self._tools.values())

    def match(self, query: str) -> MCPToolDefinition | None:
        for tool in self._tools.values():
            if tool.enabled and tool.matches(query):
                return tool
        return None


_registry: MCPRegistry | None = None
_defaults_registered = False


def get_mcp_registry() -> MCPRegistry:
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry


def register_default_mcp_tools() -> MCPRegistry:
    global _defaults_registered
    registry = get_mcp_registry()
    if _defaults_registered:
        return registry

    registry.extend(
        [
            MCPToolDefinition(
                name="debug.echo",
                description="回显当前请求，方便联调入参与链路。",
                tags=("echo", "回显", "debug", "调试"),
                input_schema={"message": "string"},
            ),
            MCPToolDefinition(
                name="debug.session_context",
                description="返回当前会话、用户和历史上下文摘要。",
                tags=("session", "context", "上下文", "会话"),
            ),
            MCPToolDefinition(
                name="utility.keyword_extract",
                description="从输入文本中提取关键词。",
                tags=("关键词", "keyword", "extract", "提取"),
                input_schema={"text": "string"},
            ),
            MCPToolDefinition(
                name="utility.sum_numbers",
                description="对输入中的数字执行求和。",
                tags=("sum", "加总", "求和", "总和"),
                input_schema={"numbers": "number[]"},
            ),
        ]
    )
    _defaults_registered = True
    return registry
