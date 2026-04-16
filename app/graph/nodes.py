from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_json, set_json
from app.memory.history_loader import HistoryEntry, get_history_loader
from app.providers.factories import LLMProviderFactory
from app.repositories.chat import GraphCheckpointRepository, MessageRepository
from app.schemas.provider import LLMMessage


async def init_request(state: dict) -> dict:
    message = state["user_message"]
    return {
        "normalized_query": " ".join(message.split()),
        "trace_id": state.get("trace_id") or str(uuid4()),
        "request_id": state.get("request_id") or str(uuid4()),
        "recall_count": 0,
        "top_k": 5,
        "retrieved_docs": [],
        "relevance_score": 0.0,
        "cache_hit": False,
        "cache_context": {},
        "need_web_fallback": False,
        "usage": {},
        "stream_chunks": [],
        "graph_run_id": str(uuid4()),
        "web_search_results": [],
        "web_search_query": "",
    }


def load_session_context_factory(message_repo: MessageRepository):
    async def load_session_context(state: dict) -> dict:
        # 从 PostgreSQL 加载全量历史
        db_messages = await message_repo.list_by_session(state["session_id"], limit=100)
        pg_entries = [HistoryEntry(role=m.role, content=m.content, metadata={}) for m in db_messages]

        # 通过 HistoryLoader 加载：先查 Redis，miss 时用 pg_entries 回填
        history_loader = get_history_loader()
        history_messages = await history_loader.load_history(
            state["session_id"],
            user_id=state.get("user_id"),
            pg_messages=pg_entries,
        )
        llm_messages = [*history_messages, LLMMessage(role="user", content=state["user_message"])]
        return {
            "history_messages": history_messages,
            "llm_messages": llm_messages,
        }

    return load_session_context


async def check_window_cache(state: dict) -> dict:
    """检查缓存：先精确匹配，再做语义相似匹配。"""
    from app.memory.window_cache import get_window_cache_service

    cache_service = get_window_cache_service()
    session_id = state["session_id"]
    normalized_query = state["normalized_query"]
    user_id = state.get("user_id")

    # 1. 精确匹配
    exact_hit = await cache_service.check_exact_hit(session_id, normalized_query, user_id=user_id)
    if exact_hit:
        return {
            "cache_hit": True,
            "cache_context": {
                "query": exact_hit.query,
                "response_text": exact_hit.response_text,
                "similarity": exact_hit.similarity,
                "match_type": "exact",
            },
            "response_text": exact_hit.response_text,
            "provider_name": exact_hit.provider,
            "route_type": exact_hit.route_type,
            "finish_reason": None,
            "usage": exact_hit.usage,
        }

    # 2. 语义相似匹配
    sim_hit = await cache_service.check_similarity_hit(session_id, normalized_query, user_id=user_id)
    if sim_hit:
        return {
            "cache_hit": True,
            "cache_context": {
                "query": sim_hit.query,
                "response_text": sim_hit.response_text,
                "similarity": sim_hit.similarity,
                "match_type": "similarity",
            },
            "response_text": sim_hit.response_text,
            "provider_name": sim_hit.provider,
            "route_type": sim_hit.route_type,
            "finish_reason": None,
            "usage": sim_hit.usage,
        }

    return {"cache_hit": False, "cache_context": {}}


async def supervisor_route(state: dict) -> dict:
    if state.get("cache_hit"):
        return {}

    query = state["normalized_query"].lower()
    route_type = "smalltalk"
    need_web_fallback = False
    if any(token in query for token in ("http", "网址", "新闻", "今天", "搜索", "web")):
        route_type = "web_search"
        need_web_fallback = True
    elif any(token in query for token in ("知识库", "文档", "kb", "rag", "资料")):
        route_type = "knowledge_qa"

    return {"route_type": route_type, "need_web_fallback": need_web_fallback}


def _system_prompt(route_type: str, need_web_fallback: bool) -> str:
    if route_type == "knowledge_qa":
        return "你是知识库问答助手。当前知识检索能力尚在建设中，请基于已有上下文给出谨慎、清晰的回答，并明确缺失信息。"
    if route_type == "web_search":
        fallback = "当前未接入实时联网搜索，请明确说明这是离线回答。" if need_web_fallback else ""
        return f"你是网页检索助手。{fallback}".strip()
    return "你是一个友好、简洁的智能助手。"


async def generate_response(state: dict) -> dict:
    if state.get("cache_hit"):
        return {"stream_chunks": []}

    provider = LLMProviderFactory.create()
    llm_messages = [*state.get("history_messages", [])]
    llm_messages.insert(0, LLMMessage(role="system", content=_system_prompt(state["route_type"], state["need_web_fallback"])))
    llm_messages.append(LLMMessage(role="user", content=state["user_message"]))

    if state.get("stream"):
        aggregated = ""
        stream_chunks: list[dict] = []
        finish_reason: str | None = None
        async for chunk in provider.stream_chat(llm_messages, model=state.get("model")):
            if chunk.delta:
                aggregated += chunk.delta
                stream_chunks.append(chunk.model_dump())
            finish_reason = chunk.finish_reason or finish_reason
        return {
            "response_text": aggregated,
            "provider_name": provider.provider_name,
            "model": stream_chunks[-1]["model"] if stream_chunks else state.get("model"),
            "finish_reason": finish_reason,
            "stream_chunks": stream_chunks,
        }

    result = await provider.chat(llm_messages, model=state.get("model"))
    return {
        "response_text": result.content,
        "provider_name": result.provider,
        "model": result.model,
        "finish_reason": result.finish_reason,
        "usage": result.usage,
    }


async def post_process(state: dict) -> dict:
    response_text = state.get("response_text", "").strip()
    return {"response_text": response_text or "抱歉，我暂时无法生成有效回复。"}


def persist_state_factory(
    checkpoint_repo: GraphCheckpointRepository,
    message_repo: MessageRepository,
    session: AsyncSession,
):
    async def persist_state(state: dict) -> dict:
        await message_repo.create(
            session_id=state["session_id"],
            role="user",
            content=state["user_message"],
            user_id=state["user_id"],
            model=state.get("model"),
            metadata={"username": state.get("username")},
        )
        await message_repo.create(
            session_id=state["session_id"],
            role="assistant",
            content=state["response_text"],
            user_id=state["user_id"],
            model=state.get("model"),
            token_usage=state.get("usage") or {},
            metadata={
                "provider": state.get("provider_name"),
                "finish_reason": state.get("finish_reason"),
                "route_type": state.get("route_type"),
                "cache_hit": state.get("cache_hit", False),
            },
        )

        # 更新 Redis 热窗口（最近 N 条消息）
        history_loader = get_history_loader()
        await history_loader.save_to_window(
            state["session_id"],
            [
                HistoryEntry(role="user", content=state["user_message"]),
                HistoryEntry(role="assistant", content=state["response_text"]),
            ],
            user_id=state.get("user_id"),
        )

        # 缓存当前 query→response 映射（用于 check_window_cache 精确匹配）
        from app.core.config import get_settings

        settings = get_settings()
        cache_key = f"{settings.cache.prefix}:query_cache:{state['session_id']}:{state['normalized_query']}"
        cache_payload = {
            "query": state["normalized_query"],
            "response_text": state["response_text"],
            "provider": state.get("provider_name"),
            "route_type": state.get("route_type"),
            "finish_reason": state.get("finish_reason"),
            "usage": state.get("usage") or {},
        }
        await set_json(cache_key, cache_payload)

        # 保存到语义相似缓存（embedding 窗口）
        from app.memory.window_cache import get_window_cache_service

        window_cache = get_window_cache_service()
        await window_cache.save_cache(
            state["session_id"],
            state["normalized_query"],
            state["response_text"],
            user_id=state.get("user_id"),
            route_type=state.get("route_type", "smalltalk"),
            provider=state.get("provider_name", ""),
            usage=state.get("usage") or {},
        )

        checkpoint_state = {
            "trace_id": state.get("trace_id"),
            "request_id": state.get("request_id"),
            "session_id": state.get("session_id"),
            "user_id": state.get("user_id"),
            "username": state.get("username"),
            "normalized_query": state.get("normalized_query"),
            "route_type": state.get("route_type"),
            "cache_hit": state.get("cache_hit"),
            "need_web_fallback": state.get("need_web_fallback"),
            "response_text": state.get("response_text"),
            "usage": state.get("usage") or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await checkpoint_repo.create(
            session_id=state["session_id"],
            checkpoint_ns="main_graph",
            checkpoint_id=state["graph_run_id"],
            parent_checkpoint_id=None,
            state=checkpoint_state,
            metadata={"route_type": state.get("route_type"), "cache_hit": state.get("cache_hit", False)},
        )
        await session.commit()
        return {}

    return persist_state


def route_by_type(state: dict) -> str:
    if state.get("cache_hit"):
        return "post_process"
    return state.get("route_type", "smalltalk")


# ------------------------------------------------------------------
# 自管理 session 的节点（用于 checkpointer 模式）
# ------------------------------------------------------------------


async def load_session_context_with_self_session(state: dict) -> dict:
    """load_session_context 的自管理 session 版本。

    当主图使用 checkpointer 模式（无外部注入 session）时，
    每个需要数据库访问的节点需要自行创建/释放 session。

    三层记忆架构：
    1. 摘要层 — 早期历史经 LLM 压缩
    2. 近期窗口 — 最近 N 条原始消息
    3. 当前消息 — 用户本轮提问
    """
    from app.db.models import Session as SessionModel
    from app.db.session import get_sessionmaker
    from app.memory.summary_memory import get_summary_memory_service
    from app.repositories.chat import MessageRepository

    async with get_sessionmaker()() as session:
        # 1. 加载会话和全量历史
        from sqlalchemy import select

        chat_session = await session.get(SessionModel, state["session_id"])
        existing_summary = None
        if chat_session and chat_session.metadata_:
            existing_summary = chat_session.metadata_.get("summary")

        message_repo = MessageRepository(session)
        db_messages = await message_repo.list_by_session(state["session_id"], limit=200)
        all_messages = [{"role": m.role, "content": m.content, "id": m.id} for m in db_messages]

        # 2. 检查是否需要压缩历史
        summary_service = get_summary_memory_service()
        new_summary = await summary_service.check_and_compress(
            all_messages,
            session_id=state["session_id"],
            existing_summary=existing_summary,
        )

        # 3. 如果生成了新摘要，更新 session
        if new_summary:
            if chat_session is None:
                chat_session = await session.get(SessionModel, state["session_id"])
            if chat_session:
                chat_session.metadata_["summary"] = new_summary
                existing_summary = new_summary
                await session.flush()

        # 4. 加载三层记忆
        memory = summary_service.load_memory(all_messages, summary=existing_summary)

        # 5. 构建完整的 llm_messages
        llm_messages: list[LLMMessage] = []

        # Layer 1: 摘要作为 system context
        if memory.summary:
            llm_messages.append(
                LLMMessage(
                    role="system",
                    content=f"以下是之前对话的摘要，请参考以保持上下文连贯：\n\n{memory.summary}",
                )
            )

        # Layer 2: 近期原始消息
        llm_messages.extend(memory.recent_messages)

        # 当前用户消息
        llm_messages.append(LLMMessage(role="user", content=state["user_message"]))

        # 6. 同时更新 Redis 热窗口
        pg_entries = [HistoryEntry(role=m["role"], content=m["content"]) for m in all_messages]
        history_loader = get_history_loader()
        history_messages = await history_loader.load_history(
            state["session_id"],
            user_id=state.get("user_id"),
            pg_messages=pg_entries,
        )

        await session.commit()

        return {
            "history_messages": history_messages,
            "llm_messages": llm_messages,
        }


async def persist_state_with_self_session(state: dict) -> dict:
    """persist_state 的自管理 session 版本。"""
    from app.db.session import get_sessionmaker
    from app.repositories.chat import GraphCheckpointRepository, MessageRepository

    async with get_sessionmaker()() as session:
        message_repo = MessageRepository(session)
        checkpoint_repo = GraphCheckpointRepository(session)

        await message_repo.create(
            session_id=state["session_id"],
            role="user",
            content=state["user_message"],
            user_id=state["user_id"],
            model=state.get("model"),
            metadata={"username": state.get("username")},
        )
        await message_repo.create(
            session_id=state["session_id"],
            role="assistant",
            content=state["response_text"],
            user_id=state["user_id"],
            model=state.get("model"),
            token_usage=state.get("usage") or {},
            metadata={
                "provider": state.get("provider_name"),
                "finish_reason": state.get("finish_reason"),
                "route_type": state.get("route_type"),
                "cache_hit": state.get("cache_hit", False),
            },
        )

        # 更新 Redis 热窗口
        history_loader = get_history_loader()
        await history_loader.save_to_window(
            state["session_id"],
            [
                HistoryEntry(role="user", content=state["user_message"]),
                HistoryEntry(role="assistant", content=state["response_text"]),
            ],
            user_id=state.get("user_id"),
        )

        # 缓存 query→response
        from app.core.config import get_settings

        settings = get_settings()
        cache_key = f"{settings.cache.prefix}:query_cache:{state['session_id']}:{state['normalized_query']}"
        cache_payload = {
            "query": state["normalized_query"],
            "response_text": state["response_text"],
            "provider": state.get("provider_name"),
            "route_type": state.get("route_type"),
            "finish_reason": state.get("finish_reason"),
            "usage": state.get("usage") or {},
        }
        await set_json(cache_key, cache_payload)

        # 保存到语义相似缓存（embedding 窗口）
        from app.memory.window_cache import get_window_cache_service as _get_wc

        window_cache = _get_wc()
        await window_cache.save_cache(
            state["session_id"],
            state["normalized_query"],
            state["response_text"],
            user_id=state.get("user_id"),
            route_type=state.get("route_type", "smalltalk"),
            provider=state.get("provider_name", ""),
            usage=state.get("usage") or {},
        )

        # 持久化 checkpoint
        checkpoint_state = {
            "trace_id": state.get("trace_id"),
            "request_id": state.get("request_id"),
            "session_id": state.get("session_id"),
            "user_id": state.get("user_id"),
            "username": state.get("username"),
            "normalized_query": state.get("normalized_query"),
            "route_type": state.get("route_type"),
            "cache_hit": state.get("cache_hit"),
            "need_web_fallback": state.get("need_web_fallback"),
            "response_text": state.get("response_text"),
            "usage": state.get("usage") or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await checkpoint_repo.create(
            session_id=state["session_id"],
            checkpoint_ns="main_graph",
            checkpoint_id=state["graph_run_id"],
            parent_checkpoint_id=None,
            state=checkpoint_state,
            metadata={"route_type": state.get("route_type"), "cache_hit": state.get("cache_hit", False)},
        )
        await session.commit()
        return {}
