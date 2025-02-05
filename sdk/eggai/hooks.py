import asyncio
import signal
import sys

# Global variables for shutdown handling.
_STOP_CALLBACKS = []
_EXIT_EVENT = None  # will be lazily created
_SIGNAL_HANDLERS_INSTALLED = False
_CLEANUP_STARTED = False
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
    print("EggAI: Cleaning up...", flush=True)
    for stop_coro in _STOP_CALLBACKS:
        try:
            await stop_coro()
        except Exception as e:
            print(f"Error stopping: {e}", file=sys.stderr, flush=True)
    _STOP_CALLBACKS.clear()
    print("EggAI: Cleanup done.", flush=True)


async def _install_signal_handlers():
    async def shutdown(s, cancel_tasks):
        print(f"Received {s.name} signal, exiting...", flush=True)
        await eggai_cleanup()
        if cancel_tasks:
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            [task.cancel() for task in tasks]
            await asyncio.gather(*tasks)

    global _SIGNAL_HANDLERS_INSTALLED
    if _SIGNAL_HANDLERS_INSTALLED:
        return

    loop = asyncio.get_event_loop()
    for sig in HANDLED_SIGNALS:
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(sig, False)))
        except NotImplementedError:
            signal.signal(sig, lambda _, __: asyncio.create_task(shutdown(sig, True)))


def eggai_main(func):
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

    async def wrapper(*args, **kwargs):
        await _install_signal_handlers()

        try:
            await func(*args, **kwargs)
        except asyncio.CancelledError:
            print("EggAI: Application interrupted by user.", flush=True)
            return True
        finally:
            await eggai_cleanup()
        return True

    return wrapper


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
            print("EggAI: Application interrupted by user.", flush=True)
            return True
