import asyncio
import os
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from .hooks import eggai_register_stop
from .transport import get_default_transport
from .transport.base import Transport

HANDLERS_IDS = defaultdict(int)

# Environment variable: EGGAI_NAMESPACE
# Purpose: Prefix for all channel names to enable namespace isolation in shared transports.
# Default: "eggai"
# Usage: Set EGGAI_NAMESPACE="myapp" to namespace all channels as "myapp.*"
# Example: If EGGAI_NAMESPACE="prod" and channel name is "events", the final channel is "prod.events"
# This allows multiple applications or environments to share the same Kafka/Redis cluster
# without channel name collisions.
NAMESPACE = os.getenv("EGGAI_NAMESPACE", "eggai")
DEFAULT_CHANNEL_NAME = "channel"


class Channel:
    """
    A channel that publishes messages to a given 'name' on its own Transport.
    Connection is established lazily on the first publish or subscription.
    """

    def __init__(self, name: str = None, transport: Transport | None = None):
        """
        Initialize a Channel instance.

        Args:
            name (str): The channel (topic) name. Defaults to "eggai.channel".
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
        from .tracing import _set_span_attrs, apply_traceparent, get_tracer

        tracer = get_tracer()
        if tracer is not None:
            from opentelemetry.propagate import extract as otel_extract
            from opentelemetry.propagate import inject as otel_inject
            from opentelemetry.trace import SpanKind

            # If the message already carries a traceparent, continue that trace.
            existing_tp = (
                message.get("traceparent")
                if isinstance(message, dict)
                else getattr(message, "traceparent", None)
            )
            parent_ctx = (
                otel_extract({"traceparent": existing_tp}) if existing_tp else None
            )

            with tracer.start_as_current_span(
                f"eggai.publish {self._name}",
                context=parent_ctx,
                kind=SpanKind.PRODUCER,
            ) as span:
                _set_span_attrs(span, self._name, message, "publish")
                carrier: dict = {}
                otel_inject(carrier)
                if carrier.get("traceparent"):
                    message = apply_traceparent(message, carrier["traceparent"])
                await self._get_transport().publish(self._name, message)
        else:
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
