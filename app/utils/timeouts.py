"""Deadline helper for work that must answer within a fixed budget (Vapi's tool timeout)."""

import asyncio
from collections.abc import Awaitable


async def run_with_timeout[T](awaitable: Awaitable[T], seconds: float) -> T:
    """Await `awaitable`, raising TimeoutError (and cancelling the work) after `seconds`."""
    async with asyncio.timeout(seconds):
        return await awaitable
