from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging import get_logger


logger = get_logger("app.runtime")
T = TypeVar("T")


class ConcurrencyController:
    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def get(self, name: str, limit: int) -> asyncio.Semaphore:
        semaphore = self._semaphores.get(name)
        if semaphore is None:
            semaphore = asyncio.Semaphore(max(1, limit))
            self._semaphores[name] = semaphore
        return semaphore

    async def run(self, name: str, limit: int, operation: Callable[[], Awaitable[T]]) -> T:
        semaphore = self.get(name, limit)
        async with semaphore:
            return await operation()


_controller: ConcurrencyController | None = None


def get_concurrency_controller() -> ConcurrencyController:
    global _controller
    if _controller is None:
        _controller = ConcurrencyController()
    return _controller


async def run_with_timeout(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float,
    timeout_message: str,
) -> T:
    try:
        return await asyncio.wait_for(operation(), timeout=timeout_seconds)
    except TimeoutError as exc:
        logger.warning("runtime.timeout", extra={"detail": timeout_message, "timeout_seconds": timeout_seconds})
        raise TimeoutError(timeout_message) from exc
