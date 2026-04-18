from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.chat import ChatDebugResponse, ChatHistoryResponse, ChatResponse
from app.services.chat import ChatService


async def _fake_session() -> AsyncIterator[None]:
    yield None


@pytest.fixture(autouse=True)
def _override_db() -> AsyncIterator[None]:
    app.dependency_overrides[get_db_session] = _fake_session
    yield
    app.dependency_overrides.clear()


def test_chat_endpoint_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self: ChatService, payload) -> ChatResponse:
        return ChatResponse(
            session_id="session-1",
            user_id="user-1",
            model="mock-echo",
            content="hello",
            provider="mock",
            route_type="smalltalk",
            cache_hit=False,
            finish_reason="stop",
            usage={},
        )

    monkeypatch.setattr(ChatService, "chat", fake_chat)

    client = TestClient(app)
    response = client.post("/api/v1/chat", json={"username": "tester", "message": "hello"})
    assert response.status_code == 200
    assert response.json()["content"] == "hello"


def test_chat_debug_endpoint_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_debug(self: ChatService, session_id: str, *, limit: int = 50) -> ChatDebugResponse:
        return ChatDebugResponse(
            session_id=session_id,
            user_id="user-1",
            graph_state={"route_type": "mcp_call"},
            context={"history_count": 2},
            recall_items=[],
            cache_info={"hit": False},
            tool_calls=[],
            api_response={"content": "ok"},
            rendered_payload={"summary": "ok"},
            timeline=[],
        )

    monkeypatch.setattr(ChatService, "debug", fake_debug)

    client = TestClient(app)
    response = client.get("/api/v1/chat/debug", params={"session_id": "550e8400-e29b-41d4-a716-446655440000"})
    assert response.status_code == 200
    assert response.json()["graph_state"]["route_type"] == "mcp_call"
