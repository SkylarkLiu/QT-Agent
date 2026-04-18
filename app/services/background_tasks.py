from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.runtime import run_with_timeout


logger = get_logger("app.services.background")


class BackgroundTaskDispatcher:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def dispatch(
        self,
        name: str,
        operation: Callable[[], Awaitable[Any]],
        *,
        timeout_seconds: int | None = None,
    ) -> asyncio.Task[Any]:
        settings = get_settings()
        timeout = timeout_seconds or settings.runtime.background_task_timeout_seconds

        async def runner() -> Any:
            try:
                return await run_with_timeout(
                    operation,
                    timeout_seconds=timeout,
                    timeout_message=f"Background task '{name}' timed out.",
                )
            except Exception:
                logger.exception("background_task.failed", extra={"task_name": name})
                raise

        task = asyncio.create_task(runner(), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task


_dispatcher: BackgroundTaskDispatcher | None = None


def get_background_task_dispatcher() -> BackgroundTaskDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = BackgroundTaskDispatcher()
    return _dispatcher
