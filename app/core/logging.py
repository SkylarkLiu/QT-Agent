from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


trace_id_var = contextvars.ContextVar("trace_id", default="-")
request_id_var = contextvars.ContextVar("request_id", default="-")
session_id_var = contextvars.ContextVar("session_id", default="-")
user_id_var = contextvars.ContextVar("user_id", default="-")


def set_log_context(*, trace_id: str | None = None, request_id: str | None = None, session_id: str | None = None, user_id: str | None = None) -> None:
    if trace_id is not None:
        trace_id_var.set(trace_id)
    if request_id is not None:
        request_id_var.set(request_id)
    if session_id is not None:
        session_id_var.set(session_id)
    if user_id is not None:
        user_id_var.set(user_id)


def clear_log_context() -> None:
    set_log_context(trace_id="-", request_id="-", session_id="-", user_id="-")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "log_type": getattr(record, "log_type", "business"),
            "trace_id": trace_id_var.get(),
            "request_id": request_id_var.get(),
            "session_id": session_id_var.get(),
            "user_id": user_id_var.get(),
        }

        for field in ("method", "path", "status_code", "duration_ms", "service_name", "service_host", "service_port", "attempt", "app_env", "app_name", "startup_retry_enabled"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_qt_agent_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
    root_logger._qt_agent_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        session_id = request.headers.get("X-Session-Id", "-")
        user_id = request.headers.get("X-User-Id", "-")

        set_log_context(trace_id=trace_id, request_id=request_id, session_id=session_id, user_id=user_id)

        logger = get_logger("app.access")
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            error_logger = get_logger("app.error")
            error_logger.exception(
                "request.failed",
                extra={"log_type": "error", "method": request.method, "path": request.url.path},
            )
            clear_log_context()
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Request-Id"] = request_id

        logger.info(
            "request.completed",
            extra={
                "log_type": "access",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        clear_log_context()
        return response
