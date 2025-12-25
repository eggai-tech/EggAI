import asyncio
import logging
import signal
import sys
from typing import Callable, Coroutine, Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Coroutine[Any, Any, Any]])

# Global variables for shutdown handling.
_STOP_CALLBACKS = []
_EXIT_EVENT = None  # will be lazily created
_SIGNAL_HANDLERS_INSTALLED = False
_CLEANUP_STARTED = False
_GLOBAL_TASK = None
HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)
if sys.platform == "win32":  # pragma: py-not-win32
    HANDLED_SIGNALS += (signal.SIGBREAK,)  # Windows only signal. Sent by Ctrl+Break.


def _get_exit_event():
    """Return (and create if needed) the global exit event."""
    global _EXIT_EVENT
    if _EXIT_EVENT is None:
        _EXIT_EVENT = asyncio.Event()
    return _EXIT_EVENT


async def eggai_register_stop(stop_coro):
    """
    Register a coroutine (e.g. agent.stop) to be awaited during shutdown.

    :param stop_coro: A coroutine function that will be awaited during shutdown.

    Example:

    ```python
    async def stop():
        await agent.stop()

    await eggai_register_stop(stop)
    ```
    """
    _STOP_CALLBACKS.append(stop_coro)


async def eggai_cleanup():
    """
    Await all registered stop callbacks.
    """
    global _STOP_CALLBACKS, _CLEANUP_STARTED
    if _CLEANUP_STARTED:
        return
    _CLEANUP_STARTED = True
    logger.info("EggAI: Cleaning up...")
    for stop_coro in _STOP_CALLBACKS:
        try:
            await stop_coro()
        except Exception as e:
            logger.error(f"Error stopping: {e}")
    _STOP_CALLBACKS.clear()
    logger.info("EggAI: Cleanup done.")


async def _install_signal_handlers():
    async def shutdown(s, cancel_tasks):
        if _GLOBAL_TASK is not None:
            _GLOBAL_TASK.cancel()
        # if cancel_tasks:
        #     tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        #     [task.cancel() for task in tasks]
        #     await asyncio.gather(*tasks)

    global _SIGNAL_HANDLERS_INSTALLED
    if _SIGNAL_HANDLERS_INSTALLED:
        return

    loop = asyncio.get_event_loop()
    for sig in HANDLED_SIGNALS:
        try:
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(shutdown(sig, False))
            )
        except NotImplementedError:
            signal.signal(sig, lambda _, __: asyncio.create_task(shutdown(sig, True)))


def eggai_main(func: F) -> F:
    """
    Decorator for your main function.

    This decorator installs the signal handlers, runs your main function
    concurrently with waiting on the exit event, and when a shutdown signal
    is received (or the main function returns) it will automatically run eggai cleanup.

    Use it like this:

    ```python
        @eggai_main
        async def main():
            await agent.start()
            ...
    ```

    Note: if you want to keep the program running forever until interrupted,
    you can add `await asyncio.Future()` at the end of your main function.
    """

    async def wrapper(*args: Any, **kwargs: Any) -> bool:
        await _install_signal_handlers()
        global _GLOBAL_TASK

        if _GLOBAL_TASK is not None:
            raise RuntimeError("eggai_main can only be used once per program.")

        try:
            _GLOBAL_TASK = asyncio.create_task(func(*args, **kwargs))
            await _GLOBAL_TASK
        except asyncio.CancelledError:
            logger.info("EggAI: Application interrupted by user.")
            return True
        finally:
            await eggai_cleanup()
        return True

    return wrapper  # type: ignore[return-value]


class EggaiRunner:
    """
    Context manager for running an EggAI application.

    This class installs signal handlers and runs the cleanup process when the context exits.
    Use it like this:

    ```python
        async with EggaiRunner():
            await agent.start()
            ...
    ```

    Note: if you want to keep the program running forever until interrupted,
    you can add `await asyncio.Future()` at the end of your main function.
    """

    async def __aenter__(self):
        await _install_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await eggai_cleanup()
        if exc_type == asyncio.CancelledError:
            logger.info("EggAI: Application interrupted by user.")
            return True
