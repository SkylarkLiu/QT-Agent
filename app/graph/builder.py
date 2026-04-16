from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from app.graph.nodes import (
    check_window_cache,
    generate_response,
    init_request,
    load_session_context_factory,
    persist_state_factory,
    post_process,
    route_by_type,
    supervisor_route,
)
from app.graph.rag_builder import build_rag_subgraph
from app.graph.state import GraphState
from app.graph.web_builder import build_web_search_subgraph
from app.memory.checkpointer import PostgresCheckpointer
from app.repositories.chat import GraphCheckpointRepository, MessageRepository


def _route_after_knowledge_qa(state: dict) -> str:
    """knowledge_qa 节点后的路由：检查是否需要降级到 web_search。

    RAG 子图在知识库低命中时会设置 need_web_fallback=True，
    主图需要检测这个标志并跳转到 web_search 子图。
    """
    if state.get("need_web_fallback"):
        return "web_search"
    return "post_process"


def build_main_graph(session: AsyncSession | None = None):
    """编译主图，可选注入 checkpointer。

    Args:
        session: 当传入 session 时，使用 session-scoped 的 repos（向后兼容）。
                 当为 None 时，使用 checkpointer 模式（session 由 checkpointer 自管理）。
    """
    use_checkpointer = session is None

    if use_checkpointer:
        # Checkpointer 模式：每个节点需要自管理 session
        checkpointer = PostgresCheckpointer(get_sessionmaker)
        message_repo = None
        checkpoint_repo = None
    else:
        # Legacy 模式：外部注入 session
        checkpointer = None
        message_repo = MessageRepository(session)
        checkpoint_repo = GraphCheckpointRepository(session)

    # 构建子图并编译
    rag_subgraph = build_rag_subgraph().compile()
    web_search_subgraph = build_web_search_subgraph().compile()

    builder = StateGraph(GraphState)
    builder.add_node("init_request", init_request)

    # load_session_context：checkpointer 模式下自管理 session
    if use_checkpointer:
        from app.graph.nodes import load_session_context_with_self_session
        builder.add_node("load_session_context", load_session_context_with_self_session)
    else:
        builder.add_node("load_session_context", load_session_context_factory(message_repo))

    builder.add_node("check_window_cache", check_window_cache)
    builder.add_node("supervisor_route", supervisor_route)
    builder.add_node("smalltalk", generate_response)
    builder.add_node("knowledge_qa", rag_subgraph)
    builder.add_node("web_search", web_search_subgraph)
    builder.add_node("post_process", post_process)

    if use_checkpointer:
        from app.graph.nodes import persist_state_with_self_session
        builder.add_node("persist_state", persist_state_with_self_session)
    else:
        builder.add_node("persist_state", persist_state_factory(checkpoint_repo, message_repo, session))

    builder.add_edge(START, "init_request")
    builder.add_edge("init_request", "load_session_context")
    builder.add_edge("load_session_context", "check_window_cache")
    builder.add_edge("check_window_cache", "supervisor_route")
    builder.add_conditional_edges(
        "supervisor_route",
        route_by_type,
        {
            "smalltalk": "smalltalk",
            "knowledge_qa": "knowledge_qa",
            "web_search": "web_search",
            "post_process": "post_process",
        },
    )
    builder.add_edge("smalltalk", "post_process")

    # knowledge_qa 完成后检查是否需要降级到 web_search
    builder.add_conditional_edges(
        "knowledge_qa",
        _route_after_knowledge_qa,
        {
            "web_search": "web_search",
            "post_process": "post_process",
        },
    )

    builder.add_edge("web_search", "post_process")
    builder.add_edge("post_process", "persist_state")
    builder.add_edge("persist_state", END)

    # 编译时传入 checkpointer
    return builder.compile(checkpointer=checkpointer)
