from __future__ import annotations

import asyncio

import pytest

from app.utils.runtime import ConcurrencyController, run_with_timeout


@pytest.mark.asyncio
async def test_run_with_timeout_returns_result() -> None:
    result = await run_with_timeout(
        lambda: asyncio.sleep(0, result="ok"),
        timeout_seconds=1,
        timeout_message="timeout",
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_with_timeout_raises_timeout() -> None:
    with pytest.raises(TimeoutError):
        await run_with_timeout(
            lambda: asyncio.sleep(0.05),
            timeout_seconds=0.01,
            timeout_message="timeout",
        )


@pytest.mark.asyncio
async def test_concurrency_controller_serializes_single_slot() -> None:
    controller = ConcurrencyController()
    active = 0
    max_active = 0

    async def task() -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1

    await asyncio.gather(
        controller.run("embedding", 1, task),
        controller.run("embedding", 1, task),
    )
    assert max_active == 1
