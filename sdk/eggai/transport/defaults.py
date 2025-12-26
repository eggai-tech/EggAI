import logging
from collections.abc import Callable

from .base import Transport
from .inmemory import InMemoryTransport

logger = logging.getLogger(__name__)

_DEFAULT_TRANSPORT_FACTORY: Callable[[], "Transport"] | None = None


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
    If no default transport factory is set, return an InMemoryTransport instance and log a warning.
    """
    if _DEFAULT_TRANSPORT_FACTORY is None:
        logger.warning(
            "No default transport factory set, InMemoryTransport will be used. "
            "Use eggai_set_default_transport() to set a different default transport."
        )
        eggai_set_default_transport(lambda: InMemoryTransport())
    return _DEFAULT_TRANSPORT_FACTORY()
