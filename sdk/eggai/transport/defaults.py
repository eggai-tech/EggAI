import sys
from typing import Optional, Callable

from .base import Transport
from .inmemory import InMemoryTransport

_DEFAULT_TRANSPORT_FACTORY: Optional[Callable[[], "Transport"]] = None


def eggai_set_default_transport(factory: Callable[[], "Transport"]):
    """
    Set a global function that returns a fresh Transport instance.
    Agents or Channels created without an explicit transport
    will use this factory.
    """
    global _DEFAULT_TRANSPORT_FACTORY
    _DEFAULT_TRANSPORT_FACTORY = factory


def get_default_transport() -> "Transport":
    """
    Get a fresh Transport instance from the default factory.
    If no default transport factory is set, return an InMemoryTransport instance and print a warning.
    """
    if _DEFAULT_TRANSPORT_FACTORY is None:
        print(
            "EggAI: Warning, no default transport factory set, InMemoryTransport will be used. Use eggai_set_default_transport() if you don't want see this warning.",
            file=sys.stderr,
        )
        sys.stderr.flush()
        eggai_set_default_transport(lambda: InMemoryTransport())
    return _DEFAULT_TRANSPORT_FACTORY()
