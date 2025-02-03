import asyncio
import signal
import sys
import atexit

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


def _install_signal_handlers():
    global _SIGNAL_HANDLERS_INSTALLED
    if _SIGNAL_HANDLERS_INSTALLED:
        return

    loop = asyncio.get_running_loop()
    possible_signals = []
    if hasattr(signal, "SIGINT"):
        possible_signals.append(signal.SIGINT)
    if hasattr(signal, "SIGTERM"):
        possible_signals.append(signal.SIGTERM)

    def signal_handler():
        try:
            _get_exit_event().set()
        except RuntimeError:
            pass
        import sys
        try:
            sys.exit(0)
        except SystemExit:
            pass

    atexit.register(signal_handler)

    for s in possible_signals:
        try:
            loop.add_signal_handler(s, signal_handler)
        except (NotImplementedError, ValueError):
            pass  # Some platforms (or Windows) may not support signals.
    _SIGNAL_HANDLERS_INSTALLED = True


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
        _install_signal_handlers()
        exit_event = _get_exit_event()

        main_task = asyncio.create_task(func(*args, **kwargs))
        exit_wait_task = asyncio.create_task(exit_event.wait())
        try:
            done, pending = await asyncio.wait(
                [main_task, exit_wait_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
        except asyncio.CancelledError:
            print("EggAI: Application interrupted by user.", flush=True)
            exit_event.set()
            await asyncio.sleep(0.1)
        finally:
            if exit_event.is_set():
                main_task.cancel()
                try:
                    await main_task
                except asyncio.CancelledError:
                    pass
            if not exit_event.is_set():
                exit_event.set()
                await asyncio.sleep(0.1)
            await eggai_cleanup()

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
        _install_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await eggai_cleanup()
        if exc_type == asyncio.CancelledError:
            print("EggAI: Application interrupted by user.", flush=True)
            return True

