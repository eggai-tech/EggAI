from importlib.metadata import version
from typing import TYPE_CHECKING, Any

__version__ = version("eggai")

from .agent import Agent as Agent
from .channel import Channel as Channel
from .hooks import EggaiRunner as EggaiRunner
from .hooks import eggai_cleanup as eggai_cleanup
from .hooks import eggai_main as eggai_main
from .hooks import eggai_register_stop as eggai_register_stop
from .tracing import setup_tracing as setup_tracing
from .transport import InMemoryTransport as InMemoryTransport

if TYPE_CHECKING:
    from .transport import KafkaTransport as KafkaTransport
    from .transport import RedisTransport as RedisTransport


def __getattr__(name: str) -> Any:
    # KafkaTransport and RedisTransport need their extra; eggai.transport
    # imports them on first use and says which extra is missing.
    if name in ("KafkaTransport", "RedisTransport"):
        from . import transport

        return getattr(transport, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), "KafkaTransport", "RedisTransport"])
