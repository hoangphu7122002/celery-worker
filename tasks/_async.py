import asyncio
from collections.abc import Coroutine
from typing import TypeVar

from storage.database import engine

T = TypeVar("T")


async def _run_and_dispose(coro: Coroutine[object, object, T]) -> T:
    try:
        return await coro
    finally:
        await engine.dispose()


def run_async_task(coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(_run_and_dispose(coro))
