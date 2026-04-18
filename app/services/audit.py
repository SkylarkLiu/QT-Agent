from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger, trace_id_var
from app.repositories.chat import AuditLogRepository


logger = get_logger("app.audit")


class AuditService:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        await self.repository.create(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id or trace_id_var.get(),
            payload=payload or {},
            created_at=datetime.now(UTC),
        )
        logger.info(
            "audit.recorded",
            extra={
                "log_type": "audit",
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
