from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.chat import ChatDebugResponse, ChatHistoryQuery, ChatHistoryResponse, ChatRequest, ChatResponse
from app.services.chat import ChatService


router = APIRouter()


@router.post("/chat", summary="Chat endpoint", response_model=ChatResponse)
async def chat(payload: ChatRequest, session: AsyncSession = Depends(get_db_session)):
    service = ChatService(session)
    if payload.stream:
        return StreamingResponse(service.stream_chat(payload), media_type="text/event-stream")
    return await service.chat(payload)


@router.get("/chat/history", summary="Chat history", response_model=ChatHistoryResponse)
async def chat_history(query: ChatHistoryQuery = Depends(), session: AsyncSession = Depends(get_db_session)):
    service = ChatService(session)
    return await service.history(query.session_id, limit=query.limit)


@router.get("/chat/debug", summary="Chat debug detail", response_model=ChatDebugResponse)
async def chat_debug(query: ChatHistoryQuery = Depends(), session: AsyncSession = Depends(get_db_session)):
    service = ChatService(session)
    return await service.debug(query.session_id, limit=query.limit)
