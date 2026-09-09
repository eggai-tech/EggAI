import asyncio
import os
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from .hooks import eggai_register_stop
from .transport import get_default_transport
from .transport.base import Transport

HANDLERS_IDS: defaultdict[str, int] = defaultdict(int)

# Environment variable: EGGAI_NAMESPACE
# Purpose: Prefix for all channel names to enable namespace isolation in shared transports.
# Default: "eggai"
# Usage: Set EGGAI_NAMESPACE="myapp" to namespace all channels as "myapp.*"
# Example: If EGGAI_NAMESPACE="prod" and channel name is "events", the final channel is "prod.events"
# This allows multiple applications or environments to share the same Kafka/Redis cluster
# without channel name collisions.
NAMESPACE = os.getenv("EGGAI_NAMESPACE", "eggai")
DEFAULT_CHANNEL_NAME = "channel"


def resolve_dlq_channel(value: "Channel | str | None") -> str | None:
    """Turn the ``dlq_channel`` subscribe option into a full stream key.

    ``Agent.subscribe`` / ``Channel.subscribe`` accept either a :class:`Channel`
    (its namespaced name is used as-is) or a bare *topic name* — not a full
    key — which is namespaced by going through ``Channel(name)`` itself, so
    ``"dlq"`` becomes ``"<EGGAI_NAMESPACE>.dlq"``. The transport layer only ever
    sees the full key. Reusing ``Channel`` rather than re-spelling the prefix
    keeps the namespacing rule in one place (see #261/#264 for what happens
    when two places both try to prefix). Pass a ``Channel`` if you already hold
    a full key.
    """
    if value is None:
        return None
    if isinstance(value, Channel):
        return value.get_name()
    if isinstance(value, str) and value:
        # A string that already carries the namespace is almost certainly a full
        # key pasted by mistake (e.g. `dlq.get_name()`); namespacing it again
        # would route dead letters to "<ns>.<ns>.dlq", a stream nobody watches.
        # Fail loudly instead: the Channel form exists for full keys.
        if value.startswith(f"{NAMESPACE}."):
            raise ValueError(
                f"dlq_channel {value!r} already starts with the namespace "
                f"{NAMESPACE!r}; pass the bare topic name "
                f"({value[len(NAMESPACE) + 1 :]!r}) or a Channel instance."
            )
        # Channel.__init__ is inert (transport is lazy, no stop hook until it
        # connects), so this is a pure name computation.
        return Channel(value).get_name()
    raise ValueError(
        f"dlq_channel must be a Channel or a non-empty topic name string, got {value!r}"
    )


class Channel:
    """
    A channel that publishes messages to a given 'name' on its own Transport.
    Connection is established lazily on the first publish or subscription.
    """

    def __init__(self, name: str | None = None, transport: Transport | None = None):
        """
        Initialize a Channel instance.

        Args:
            name (str): The channel (topic) name. Defaults to "<namespace>.channel".
            transport (Optional[Transport]): A concrete transport instance. If None, a default transport is used.
        """
        self._name = f"{NAMESPACE}.{name or DEFAULT_CHANNEL_NAME}"
        self._transport = transport
        self._connected = False
        self._stop_registered = False

    def get_name(self) -> str:
        """
        Get the channel name.

        Returns:
            str: The channel name.
        """
        return self._name

    def _get_transport(self):
        if self._transport is None:
            self._transport = get_default_transport()
        return self._transport

    async def _ensure_connected(self):
        if not self._connected:
            await self._get_transport().connect()
            self._connected = True
            if not self._stop_registered:
                await eggai_register_stop(self.stop)
                self._stop_registered = True

    async def publish(self, message: dict[str, Any] | BaseModel):
        """
        Publish a message to the channel. Establishes a connection if not already connected.

        Args:
            message (Dict[str, Any]): The message payload to publish.
        """
        await self._ensure_connected()
        from .tracing import _set_span_attrs, apply_traceparent, get_backend

        backend = get_backend()
        if backend is None:
            await self._get_transport().publish(self._name, message)
            return

        with backend.start_producer_span(self._name, message) as (span, carrier):
            _set_span_attrs(span, self._name, message, "publish")
            if carrier.get("traceparent"):
                message = apply_traceparent(message, carrier["traceparent"])
            await self._get_transport().publish(self._name, message)

    async def subscribe(
        self, callback: Callable[[dict[str, Any]], "asyncio.Future"], **kwargs
    ):
        """
        Subscribe to the channel by registering a callback to be invoked when messages are received.

        Args:
            callback (Callable[[Dict[str, Any]], "asyncio.Future"]): The callback to invoke on new messages.
        """
        handler_name = (
            self._name
            + "-"
            + (callback.__name__ or "handler").replace("<", "").replace(">", "")
        )
        HANDLERS_IDS[handler_name] += 1
        kwargs["handler_id"] = f"{handler_name}-{HANDLERS_IDS[handler_name]}"
        if kwargs.get("dlq_channel") is not None:
            kwargs["dlq_channel"] = resolve_dlq_channel(kwargs["dlq_channel"])
        await self._get_transport().subscribe(self._name, callback, **kwargs)
        await self._ensure_connected()

    async def ensure_exists(self):
        """
        Ensure the channel/topic exists without publishing or subscribing.
        Useful for Kafka where topics need to exist before consumers start.
        """
        await self._get_transport().ensure_topic(self._name)

    async def stop(self):
        """
        Disconnects the channel's transport if connected.
        """
        if self._connected:
            await self._get_transport().disconnect()
            self._connected = False
