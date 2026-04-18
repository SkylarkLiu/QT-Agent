from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.provider import LLMMessage


class GraphState(TypedDict, total=False):
    trace_id: str
    request_id: str
    session_id: str
    user_id: str
    username: str

    user_message: str
    normalized_query: str
    rewritten_query: str
    model: str | None
    route_mode: str
    stream: bool

    route_type: str
    selected_skill: str
    available_skills: list[dict[str, Any]]
    mcp_tool_name: str
    mcp_arguments: dict[str, Any]
    mcp_tool_result: dict[str, Any]
    available_mcp_tools: list[dict[str, Any]]
    recall_count: int
    top_k: int
    retrieved_docs: list[dict[str, Any]]
    relevance_score: float

    cache_hit: bool
    cache_context: dict[str, Any]
    need_web_fallback: bool
    response_text: str
    finish_reason: str | None
    provider_name: str
    usage: dict[str, Any]

    web_search_results: list[dict[str, Any]]
    web_search_query: str

    history_messages: list[LLMMessage]
    llm_messages: list[LLMMessage]
    stream_chunks: list[dict[str, Any]]
    graph_run_id: str
