from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.audit import AuditService


@dataclass
class FakeAuditRepository:
    calls: list[dict[str, Any]]

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return kwargs


@pytest.mark.asyncio
async def test_audit_service_records_entry() -> None:
    repository = FakeAuditRepository(calls=[])
    service = AuditService(repository)  # type: ignore[arg-type]

    await service.record(
        action="chat.completed",
        resource_type="session",
        resource_id="session-1",
        user_id="user-1",
        payload={"route_type": "smalltalk"},
        trace_id="trace-1",
    )

    assert len(repository.calls) == 1
    call = repository.calls[0]
    assert call["action"] == "chat.completed"
    assert call["resource_type"] == "session"
    assert call["resource_id"] == "session-1"
    assert call["trace_id"] == "trace-1"
