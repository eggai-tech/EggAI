import importlib
from typing import TYPE_CHECKING, Any

from .base import Transport as Transport
from .defaults import (
    eggai_set_default_transport as eggai_set_default_transport,
)
from .defaults import (
    get_default_transport as get_default_transport,
)
from .inmemory import InMemoryTransport as InMemoryTransport
from .lease_options import LeaseLostError as LeaseLostError
from .lease_options import ProcessingTimeoutError as ProcessingTimeoutError

if TYPE_CHECKING:
    from .kafka import KafkaTransport as KafkaTransport
    from .redis import RedisTransport as RedisTransport

# The broker transports need their extra ("eggai[kafka]", "eggai[redis]"), so
# they are imported on first use: the core works with neither broker installed.
# Name -> (module, extra, the packages the extra installs).
_BROKER_TRANSPORTS = {
    "KafkaTransport": (".kafka", "kafka", ("faststream", "aiokafka")),
    "RedisTransport": (".redis", "redis", ("faststream", "redis")),
}


def __getattr__(name: str) -> Any:
    if name not in _BROKER_TRANSPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, extra, packages = _BROKER_TRANSPORTS[name]
    try:
        module = importlib.import_module(module_name, __name__)
    except ModuleNotFoundError as e:
        # Only a missing broker package means a missing extra; any other
        # missing module is a real error and stays as it is.
        if (e.name or "").split(".")[0] not in packages:
            raise
        raise ImportError(
            f"{name} needs the {extra!r} extra: pip install 'eggai[{extra}]'"
        ) from e
    transport = getattr(module, name)
    globals()[name] = transport
    return transport


def __dir__() -> list[str]:
    return sorted([*globals(), *_BROKER_TRANSPORTS])
