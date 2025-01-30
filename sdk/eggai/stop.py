import asyncio
import atexit
import signal
import sys
from typing import List, Callable

_STOP_CALLBACKS: List[Callable[[], "asyncio.Future"]] = []
_atexit_registered = False
_signal_handlers_installed = False


def register_stop(stop_coro: Callable[[], "asyncio.Future"]):
    """
    Register a coroutine (usually agent.stop() or channel.stop())
    to be awaited on shutdown.
    """
    _STOP_CALLBACKS.append(stop_coro)
    _ensure_exit_and_signal_hooks()


async def eggai_cleanup():
    """
    Stop all Agents and Channels, removing successful callbacks from the list.
    """
    global _STOP_CALLBACKS
    print("EggAI: Cleaning up...")
    for stop_coro in _STOP_CALLBACKS:
        try:
            await stop_coro()
        except Exception as e:
            print(f"Error stopping: {e}")
    _STOP_CALLBACKS.clear()

def _ensure_exit_and_signal_hooks():
    """ Make sure atexit and signal handlers are installed exactly once. """
    global _atexit_registered, _signal_handlers_installed
    if not _atexit_registered:
        atexit.register(_atexit_handler)
        _atexit_registered = True

    if not _signal_handlers_installed:
        _install_signal_handlers()
        _signal_handlers_installed = True


def _atexit_handler():
    """
    Called on normal interpreter exit (when script finishes, sys.exit(), etc.).
    We create a fresh event loop to run the async cleanup, because
    the default loop may already be closed at exit.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(eggai_cleanup())
    finally:
        loop.close()


def _install_signal_handlers():
    """
    Install handlers for SIGINT (Ctrl-C) and SIGTERM (Unix kill).
    On Windows, SIGTERM may raise NotImplementedError, so we catch that.
    """
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        print("EggAI: No event loop found, creating a new one for signal handling.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    possible_signals = []
    if hasattr(signal, "SIGINT"):
        possible_signals.append(signal.SIGINT)
    if hasattr(signal, "SIGTERM"):
        possible_signals.append(signal.SIGTERM)

    def schedule_async_cleanup():
        loop.create_task(_cleanup_and_exit())

    async def _cleanup_and_exit():
        await eggai_cleanup()
        sys.exit(0)

    for s in possible_signals:
        try:
            loop.add_signal_handler(s, schedule_async_cleanup)
        except (NotImplementedError, ValueError):
            pass
