import asyncio
import signal
import sys

# Global variables for shutdown handling.
_STOP_CALLBACKS = []
_EXIT_EVENT = None  # will be lazily created
_SIGNAL_HANDLERS_INSTALLED = False
_CLEANUP_STARTED = False


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

    if sys.platform == "win32":
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        try:
            await asyncio.gather(*tasks, return_exceptions=False)
        except asyncio.CancelledError:
            pass


async def _install_signal_handlers():
    async def shutdown(s):
        await eggai_cleanup()
        if isinstance(s, int):
            signal_name = signal.Signals(s).name
        else:
            signal_name = s.name
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks)

    global _SIGNAL_HANDLERS_INSTALLED
    if _SIGNAL_HANDLERS_INSTALLED:
        return

    signal_keys = ["SIGINT", "SIGTERM", "SIGHUP"]
    signals = []
    for key in signal_keys:
        if hasattr(signal, key):
            signals.append(getattr(signal, key))
    loop = asyncio.get_event_loop()
    for s in signals:
        try:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))
        except NotImplementedError:
            signal.signal(s, lambda _, __: asyncio.create_task(shutdown(s)))


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
