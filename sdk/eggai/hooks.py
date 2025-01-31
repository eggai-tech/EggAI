import asyncio
import atexit
import signal
import sys
from typing import List, Callable, Any, Dict

_STOP_CALLBACKS: List[Callable[[], "asyncio.Future"]] = []
_ATEXIT_REGISTERED = False
_SIGNAL_HANDLERS_INSTALLED = False

# Configuration options
_EGGAI_CONF_RUN_FOREVER_AUTO = True

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
    try:
        global _EGGAI_CONF_RUN_FOREVER_AUTO
        if _EGGAI_CONF_RUN_FOREVER_AUTO:
            print("EggAI: The program is running, press Ctrl+C to stop.", flush=True)
            await asyncio.Event().wait()
    finally:
        global _STOP_CALLBACKS
        print("EggAI: Cleaning up...", flush=True)
        for stop_coro in _STOP_CALLBACKS:
            try:
                await stop_coro()
            except Exception as e:
                print(f"Error stopping: {e}", file=sys.stderr, flush=True)
        _STOP_CALLBACKS.clear()
        print("EggAI: Cleanup done.", flush=True)

async def eggai_set_conf(conf: Dict[str, Any]):
    """
    Set configuration options for EggAI.

    :param conf: A dictionary of configuration options.

    Supported options:
    - run_forever_auto: If True, the program will run forever until interrupted.
    """
    keys = conf.keys()
    if "run_forever_auto" in keys:
        global _EGGAI_CONF_RUN_FOREVER_AUTO
        _EGGAI_CONF_RUN_FOREVER_AUTO = conf["run_forever_auto"]

def eggai_get_conf() -> Dict[str, Any]:
    """
    Get the current configuration options for EggAI.

    Supported options:
    - run_forever_auto: If True, the program will run forever until interrupted.
    """
    global _EGGAI_CONF_RUN_FOREVER_AUTO
    return {
        "run_forever_auto": _EGGAI_CONF_RUN_FOREVER_AUTO
    }

def _ensure_exit_and_signal_hooks():
    global _ATEXIT_REGISTERED, _SIGNAL_HANDLERS_INSTALLED
    if not _ATEXIT_REGISTERED:
        atexit.register(_atexit_handler)
        _ATEXIT_REGISTERED = True

    if not _SIGNAL_HANDLERS_INSTALLED:
        _install_signal_handlers()
        _SIGNAL_HANDLERS_INSTALLED = True

def _atexit_handler():
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(eggai_cleanup())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("EggAI: Application interrupted by user.", flush=True)
    finally:
        loop.close()

def _install_signal_handlers():
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        print("EggAI: No event loop found, creating a new one for signal handling.", file=sys.stderr, flush=True)
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
