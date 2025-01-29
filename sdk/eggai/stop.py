import asyncio
from typing import (
    List, Callable
)

_STOP_CALLBACKS: List[Callable[[], "asyncio.Future"]] = []

def register_stop(stop_coro: Callable[[], "asyncio.Future"]):
    """
    Register a coroutine (usually agent.stop() or channel.stop())
    to be awaited on shutdown.
    """
    _STOP_CALLBACKS.append(stop_coro)

async def eggai_stop():
    """
    Stop all Agents and Channels.
    """
    for stop_coro in _STOP_CALLBACKS:
        try:
            await stop_coro()
        except Exception as e:
            print(f"Error stopping: {e}")
