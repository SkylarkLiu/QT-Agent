from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


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

        for field in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "service_name",
            "service_host",
            "service_port",
            "attempt",
            "app_env",
            "app_name",
            "startup_retry_enabled",
            "node",
            "event",
            "status",
            "latency_ms",
            "action",
            "resource_type",
            "resource_id",
            "route_type",
            "provider",
        ):
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


class RequestContextMiddleware:
    """纯 ASGI 中间件，替代 BaseHTTPMiddleware。

    BaseHTTPMiddleware 会在独立线程中执行下游处理，请求断开时直接 cancel
    协程，导致 asyncpg 连接池 terminate 抛出 CancelledError。
    纯 ASGI 实现无此问题。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        session_id = request.headers.get("X-Session-Id", "-")
        user_id = request.headers.get("X-User-Id", "-")

        set_log_context(trace_id=trace_id, request_id=request_id, session_id=session_id, user_id=user_id)

        logger = get_logger("app.access")
        start = time.perf_counter()
        status_code = 500  # default if response never sent

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                # 注入 trace_id / request_id 到响应头
                headers = list(message.get("headers", []))
                headers.append((b"x-trace-id", trace_id.encode()))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            get_logger("app.error").exception(
                "request.failed",
                extra={
                    "log_type": "error",
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request.completed",
                extra={
                    "log_type": "access",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            clear_log_context()
