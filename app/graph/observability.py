from __future__ import annotations

from typing import Any

from app.core.logging import get_logger


logger = get_logger("app.graph.events")


def log_graph_event(
    node: str,
    *,
    event: str,
    status: str = "completed",
    latency_ms: float | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "log_type": "business",
        "node": node,
        "event": event,
        "status": status,
    }
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    payload.update(extra)
    logger.info(f"graph.{node}.{event}", extra=payload)
