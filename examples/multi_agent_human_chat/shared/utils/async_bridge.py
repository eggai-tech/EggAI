import asyncio
from typing import Awaitable, TypeVar

T = TypeVar('T')


def run_async(awaitable: Awaitable[T]) -> T:
    """
    Run an awaitable object synchronously.
    
    This is a simpler version of run_async_in_sync for when you already have
    an awaitable object (coroutine) rather than an async function to call.
    
    Args:
        awaitable: The awaitable object (coroutine) to run
        
    Returns:
        The result of the awaitable
        
    Raises:
        Any exceptions that occur during the execution of the awaitable
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(awaitable)
    finally:
        loop.close() 