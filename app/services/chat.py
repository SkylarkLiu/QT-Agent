from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, uuid5

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph import build_main_graph
from app.repositories.chat import MessageRepository, SessionRepository, UserRepository
from app.schemas.chat import ChatHistoryResponse, ChatMessageItem, ChatRequest, ChatResponse


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.session_repo = SessionRepository(session)
        self.message_repo = MessageRepository(session)

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
        return user.id, chat_session.id

    async def _run_graph(self, payload: ChatRequest) -> dict:
        user_id, session_id = await self._prepare_context(payload)
        # 使用 checkpointer 模式编译图（session=None）
        graph = build_main_graph()
        config = {
            "configurable": {
                "thread_id": session_id,
            }
        }
        state = await graph.ainvoke(
            {
                "username": payload.username,
                "user_id": user_id,
                "session_id": session_id,
                "user_message": payload.message,
                "model": payload.model,
                "stream": payload.stream,
            },
            config=config,
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
        except ValueError as exc:
            yield _sse_event("error", {"detail": str(exc)})
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
