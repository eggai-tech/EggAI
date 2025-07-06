import asyncio
import concurrent.futures
from typing import Any, Coroutine, TypeVar

from libraries.logger import get_console_logger

logger = get_console_logger("async_helpers")

T = TypeVar('T')


def run_async_safe(coro: Coroutine[Any, Any, T]) -> T:
    """Run async code safely in both sync and async contexts.
    
    This function detects whether it's being called from within an async context
    or a sync context and handles the coroutine execution appropriately.
    
    Args:
        coro: The coroutine to execute
        
    Returns:
        The result of the coroutine execution
        
    Examples:
        # From sync context:
        result = run_async_safe(some_async_function())
        
        # From async context (will use thread pool):
        result = run_async_safe(some_async_function())
    """
    try:
        # Check if we're in an async context
        loop = asyncio.get_running_loop()
        
        # We're in an async context, but we can't await directly
        # Use a thread pool to run the coroutine
        logger.debug("Running coroutine in thread pool from async context")
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
            
    except RuntimeError:
        # We're in a sync context, can use asyncio.run directly
        logger.debug("Running coroutine directly in sync context")
        return asyncio.run(coro)


async def to_async_iterator(sync_iterable):
    """Convert a synchronous iterable to an async iterator.
    
    Args:
        sync_iterable: Any synchronous iterable
        
    Yields:
        Items from the iterable
    """
    for item in sync_iterable:
        yield item


def ensure_coroutine(func_or_coro):
    """Ensure the given object is a coroutine.
    
    If it's already a coroutine, return it as-is.
    If it's a regular function result, wrap it in a coroutine.
    
    Args:
        func_or_coro: Either a coroutine or a regular value
        
    Returns:
        A coroutine that yields the value
    """
    if asyncio.iscoroutine(func_or_coro):
        return func_or_coro
    
    async def _wrapper():
        return func_or_coro
    
    return _wrapper()