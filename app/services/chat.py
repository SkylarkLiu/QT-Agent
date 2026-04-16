from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, uuid5

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph import build_main_graph
from app.repositories.chat import GraphCheckpointRepository, MessageRepository, SessionRepository, UserRepository
from app.schemas.chat import (
    ChatDebugResponse,
    ChatHistoryResponse,
    ChatMessageItem,
    ChatRequest,
    ChatResponse,
    DebugRecallItem,
    DebugTimelineItem,
    DebugToolCall,
)


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.session_repo = SessionRepository(session)
        self.message_repo = MessageRepository(session)
        self.checkpoint_repo = GraphCheckpointRepository(session)

    def _normalize_user_id(self, payload: ChatRequest) -> str:
        source = payload.user_id or payload.username
        return str(uuid5(NAMESPACE_DNS, f"qt-agent:{source}"))

    async def _prepare_context(self, payload: ChatRequest) -> tuple[str, str]:
        user = await self.user_repo.get_or_create(username=payload.username, user_id=self._normalize_user_id(payload))
        chat_session = await self.session_repo.get_or_create(
            session_id=payload.session_id,
            user_id=user.id,
            title=(payload.message[:60] if payload.message else None),
        )
        await self.session.commit()
        return user.id, chat_session.id

    async def _run_graph(self, payload: ChatRequest) -> dict:
        user_id, session_id = await self._prepare_context(payload)
        graph = build_main_graph(self.session)
        state = await graph.ainvoke(
            {
                "username": payload.username,
                "user_id": user_id,
                "session_id": session_id,
                "user_message": payload.message,
                "model": payload.model,
                "route_mode": payload.route_mode,
                "stream": payload.stream,
            }
        )
        state["user_id"] = user_id
        state["session_id"] = session_id
        return state

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        try:
            state = await self._run_graph(payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        return ChatResponse(
            session_id=state["session_id"],
            user_id=state["user_id"],
            model=state.get("model") or "unknown",
            content=state["response_text"],
            provider=state.get("provider_name") or "unknown",
            route_type=state.get("route_type"),
            cache_hit=state.get("cache_hit", False),
            finish_reason=state.get("finish_reason"),
            usage=state.get("usage") or {},
        )

    async def stream_chat(self, payload: ChatRequest) -> AsyncIterator[str]:
        try:
            state = await self._run_graph(payload)
        except Exception as exc:
            import traceback
            from app.core.logging import get_logger
            get_logger("app.chat").error(
                "stream_chat.failed",
                extra={"detail": str(exc), "type": type(exc).__name__},
            )
            yield _sse_event(
                "error",
                {
                    "detail": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()[-2000:],  # 最多 2000 字符
                },
            )
            return

        for chunk in state.get("stream_chunks", []):
            yield _sse_event(
                "delta",
                {
                    "session_id": state["session_id"],
                    "user_id": state["user_id"],
                    "model": chunk["model"],
                    "provider": chunk["provider"],
                    "delta": chunk["delta"],
                    "index": chunk["index"],
                    "route_type": state.get("route_type"),
                    "cache_hit": state.get("cache_hit", False),
                },
            )

        yield _sse_event(
            "done",
            {
                "session_id": state["session_id"],
                "user_id": state["user_id"],
                "model": state.get("model") or "unknown",
                "provider": state.get("provider_name") or "unknown",
                "content": state["response_text"],
                "finish_reason": state.get("finish_reason"),
                "route_type": state.get("route_type"),
                "cache_hit": state.get("cache_hit", False),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    async def history(self, session_id: str, *, limit: int = 50) -> ChatHistoryResponse:
        chat_session = await self.session_repo.get(session_id)
        if chat_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

        messages = await self.message_repo.list_by_session(session_id, limit=limit)
        items = [
            ChatMessageItem(
                id=message.id,
                session_id=message.session_id,
                user_id=message.user_id,
                role=message.role,
                content=message.content,
                model=message.model,
                metadata=message.metadata_,
                token_usage=message.token_usage,
                created_at=message.created_at,
            )
            for message in messages
        ]
        return ChatHistoryResponse(session_id=session_id, items=items)

    async def debug(self, session_id: str, *, limit: int = 50) -> ChatDebugResponse:
        chat_session = await self.session_repo.get(session_id)
        if chat_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

        messages = list(await self.message_repo.list_by_session(session_id, limit=limit))
        latest_checkpoint = await self.checkpoint_repo.get_latest_by_session(session_id)
        latest_state = latest_checkpoint.state if latest_checkpoint else {}

        latest_assistant = next((message for message in reversed(messages) if message.role == "assistant"), None)
        user_id = chat_session.user_id
        route_type = str(
            latest_state.get("route_type")
            or (latest_assistant.metadata_.get("route_type") if latest_assistant else None)
            or "unknown"
        )
        cache_hit = bool(
            latest_state.get("cache_hit")
            if latest_state.get("cache_hit") is not None
            else (latest_assistant.metadata_.get("cache_hit") if latest_assistant else False)
        )

        retrieved_docs = latest_state.get("retrieved_docs") or []
        web_search_results = latest_state.get("web_search_results") or []
        recall_items = self._build_recall_items(retrieved_docs, web_search_results)
        tool_calls = self._build_tool_calls(route_type, cache_hit, recall_items)
        timeline = self._build_timeline(route_type, cache_hit, recall_items, latest_assistant is not None)

        context = {
            "history_count": len(messages),
            "session_title": chat_session.title,
            "session_status": chat_session.status,
            "session_metadata": chat_session.metadata_,
            "requested_route_mode": latest_state.get("route_mode", "auto"),
            "checkpoint_id": latest_checkpoint.checkpoint_id if latest_checkpoint else None,
            "checkpoint_created_at": latest_checkpoint.created_at.isoformat() if latest_checkpoint else None,
        }
        cache_info = {
            "hit": cache_hit,
            "scope": "window",
            "key": f"qt-agent:query_cache:{session_id}:{latest_state.get('normalized_query', '')}",
            "ttl": "unknown",
            "context": latest_state.get("cache_context", {}),
        }
        api_response = {
            "session_id": session_id,
            "user_id": user_id,
            "provider": latest_assistant.metadata_.get("provider") if latest_assistant else latest_state.get("provider_name"),
            "route_type": route_type,
            "cache_hit": cache_hit,
            "finish_reason": latest_assistant.metadata_.get("finish_reason") if latest_assistant else latest_state.get("finish_reason"),
            "usage": latest_assistant.token_usage if latest_assistant else latest_state.get("usage", {}),
            "content": latest_assistant.content if latest_assistant else latest_state.get("response_text"),
        }
        rendered_payload = {
            "summary": latest_state.get("response_text") or (latest_assistant.content if latest_assistant else ""),
            "blocks": [
                {"type": "paragraph", "text": latest_state.get("response_text") or (latest_assistant.content if latest_assistant else "")},
                {
                    "type": "list",
                    "items": [
                        f"route_type: {route_type}",
                        f"cache_hit: {cache_hit}",
                        f"recall_count: {len(recall_items)}",
                    ],
                },
            ],
        }

        return ChatDebugResponse(
            session_id=session_id,
            user_id=user_id,
            graph_state=latest_state,
            context=context,
            recall_items=recall_items,
            cache_info=cache_info,
            tool_calls=tool_calls,
            api_response=api_response,
            rendered_payload=rendered_payload,
            timeline=timeline,
        )

    def _build_recall_items(
        self,
        retrieved_docs: list[dict],
        web_search_results: list[dict],
    ) -> list[DebugRecallItem]:
        if retrieved_docs:
            items: list[DebugRecallItem] = []
            for index, item in enumerate(retrieved_docs, start=1):
                items.append(
                    DebugRecallItem(
                        id=str(item.get("id") or f"recall-{index}"),
                        title=str(item.get("title") or item.get("filename") or f"document-{index}"),
                        source=str(item.get("source") or item.get("path") or "knowledge-base"),
                        score=float(item.get("score") or item.get("distance") or 0.0),
                        snippet=str(item.get("content") or item.get("snippet") or "")[:200],
                    )
                )
            return items

        items = []
        for index, item in enumerate(web_search_results, start=1):
            items.append(
                DebugRecallItem(
                    id=str(item.get("id") or f"web-{index}"),
                    title=str(item.get("title") or f"web-result-{index}"),
                    source=str(item.get("url") or item.get("source") or "web-search"),
                    score=float(item.get("score") or 0.0),
                    snippet=str(item.get("content") or item.get("snippet") or "")[:200],
                )
            )
        return items

    def _build_tool_calls(
        self,
        route_type: str,
        cache_hit: bool,
        recall_items: list[DebugRecallItem],
    ) -> list[DebugToolCall]:
        tool_calls: list[DebugToolCall] = []
        if cache_hit:
            tool_calls.append(
                DebugToolCall(
                    id="tool-cache-lookup",
                    name="window_cache.lookup",
                    target="redis",
                    status="completed",
                    latency_ms=0,
                )
            )
        if route_type == "knowledge_qa":
            tool_calls.append(
                DebugToolCall(
                    id="tool-milvus-search",
                    name="milvus.search",
                    target=f"retrieved:{len(recall_items)}",
                    status="completed",
                    latency_ms=0,
                )
            )
        if route_type == "web_search":
            tool_calls.append(
                DebugToolCall(
                    id="tool-web-search",
                    name="web.search",
                    target=f"results:{len(recall_items)}",
                    status="completed",
                    latency_ms=0,
                )
            )
        if route_type == "tool":
            tool_calls.append(
                DebugToolCall(
                    id="tool-dispatch",
                    name="tool.dispatch",
                    target="tool-router",
                    status="completed",
                    latency_ms=0,
                )
            )
        return tool_calls

    def _build_timeline(
        self,
        route_type: str,
        cache_hit: bool,
        recall_items: list[DebugRecallItem],
        has_response: bool,
    ) -> list[DebugTimelineItem]:
        now = datetime.now(UTC).strftime("%H:%M:%S")
        recall_detail = f"召回结果 {len(recall_items)} 条。"
        if route_type == "web_search":
            recall_detail = f"联网搜索结果 {len(recall_items)} 条。"
        if route_type not in {"knowledge_qa", "web_search"}:
            recall_detail = "当前分支未执行外部召回。"

        return [
            DebugTimelineItem(
                id="timeline-route",
                label="路由识别",
                status="completed",
                timestamp=now,
                detail=f"系统将请求路由到 {route_type} 分支。",
            ),
            DebugTimelineItem(
                id="timeline-recall",
                label="知识库召回",
                status="completed" if route_type in {"knowledge_qa", "web_search"} else "pending",
                timestamp=now,
                detail=recall_detail,
            ),
            DebugTimelineItem(
                id="timeline-cache",
                label="缓存检查",
                status="completed",
                timestamp=now,
                detail="命中窗口缓存。" if cache_hit else "未命中窗口缓存。",
            ),
            DebugTimelineItem(
                id="timeline-api",
                label="接口调用",
                status="completed" if has_response else "running",
                timestamp=now,
                detail="后端响应已返回。" if has_response else "正在等待模型输出。",
            ),
            DebugTimelineItem(
                id="timeline-render",
                label="渲染完成",
                status="completed" if has_response else "pending",
                timestamp=now if has_response else "--:--:--",
                detail="结构化结果已可用于前端预览。" if has_response else "等待最终渲染数据。",
            ),
        ]
