from importlib.metadata import version

__version__ = version("eggai")

from .agent import Agent as Agent
from .channel import Channel as Channel
from .hooks import (
    EggaiRunner as EggaiRunner,
)
from .hooks import (
    eggai_cleanup as eggai_cleanup,
)
from .hooks import (
    eggai_main as eggai_main,
)
from .hooks import (
    eggai_register_stop as eggai_register_stop,
)
from .transport import (
    InMemoryTransport as InMemoryTransport,
)
from .transport import (
    KafkaTransport as KafkaTransport,
)
from .transport import (
    RedisTransport as RedisTransport,
)
