import asyncio
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Callable, Tuple, TypeVar

from .channel import Channel
from .hooks import eggai_register_stop
from .transport import get_default_transport
from .transport.base import Transport

HANDLERS_IDS = defaultdict(int)

PLUGIN_LIST = ["a2a"]


T = TypeVar("T")
logger = logging.getLogger(__name__)


class Agent:
    """
    A message-based agent for subscribing to events and handling messages
    with user-defined functions.
    """

    def __init__(self, name: str, transport: Optional[Transport] = None, **kwargs):
        """
        Initializes the Agent instance.

        Args:
            name (str): The name of the agent (used as an identifier).
            transport (Optional[Transport]): A concrete transport instance (e.g., KafkaTransport, InMemoryTransport).
                If None, defaults to InMemoryTransport.
            **kwargs: Plugin-specific configuration (e.g., a2a_config for A2A plugin).
        """
        self._name = name
        self._transport = transport
        self._subscriptions: List[
            Tuple[str, Callable[[Dict[str, Any]], "asyncio.Future"], Dict]
        ] = []
        self._started = False
        self._stop_registered = False

        # Initialize plugins system
        self.plugins = {}

        # Initialize plugins generically
        for plugin_name in PLUGIN_LIST:
            plugin_kwargs = {}
            for key, value in kwargs.items():
                if key.startswith(plugin_name):
                    plugin_kwargs[key] = value

            if plugin_kwargs:
                self.plugins[plugin_name] = {}
                self.plugins[plugin_name].update(plugin_kwargs)

                if plugin_name == "a2a":
                    from .adapters.a2a.plugin import A2APlugin

                    plugin_instance = A2APlugin()
                    plugin_instance.init(self, name, transport, **kwargs)
                    self.plugins[plugin_name]["_instance"] = plugin_instance

    def _get_transport(self):
        if self._transport is None:
            self._transport = get_default_transport()
        return self._transport

    def subscribe(self, channel: Optional[Channel] = None, **kwargs):
        """
        Decorator for adding a subscription.

        Args:
            channel (Optional[Channel]): The channel to subscribe to. If None, defaults to "eggai.channel".
            **kwargs: Additional keyword arguments for the subscription and plugins.

        Returns:
            Callable: A decorator that registers the given handler for the subscription.
        """

        def decorator(handler: Callable[[Dict[str, Any]], "asyncio.Future"]):
            channel_name = channel.get_name() if channel else "eggai.channel"
            original_kwargs = kwargs.copy()

            # Extract plugin-specific kwargs dynamically and clean them from kwargs
            plugin_found_keys = set()
            for plugin_name in PLUGIN_LIST:
                for key in list(kwargs.keys()):
                    if key.startswith(plugin_name):
                        kwargs.pop(key)
                        plugin_found_keys.add(plugin_name)

            self._subscriptions.append((channel_name, handler, kwargs))

            # Call plugin subscribe methods if they have relevant kwargs
            for plugin_found_key in plugin_found_keys:
                self.plugins[plugin_found_key]["_instance"].subscribe(
                    channel_name, handler, **original_kwargs
                )

            return handler

        return decorator

    async def start(self):
        """
        Starts the agent by connecting the transport and subscribing to all registered channels.

        If no transport is provided, a default transport is used. Also registers a stop hook if not already registered.
        """
        if self._started:
            return

        for channel, handler, kwargs in self._subscriptions:
            handler_name = self._name + "-" + handler.__name__
            HANDLERS_IDS[handler_name] += 1
            kwargs["handler_id"] = f"{handler_name}-{HANDLERS_IDS[handler_name]}"
            await self._get_transport().subscribe(channel, handler, **kwargs)

        await self._get_transport().connect()
        self._started = True

        if not self._stop_registered:
            await eggai_register_stop(self.stop)
            self._stop_registered = True

    async def stop(self):
        """
        Stops the agent by disconnecting the transport.
        """
        if self._started:
            await self._get_transport().disconnect()
            self._started = False

    async def to_a2a(self, host: str = "0.0.0.0", port: int = 8080):
        await self.plugins["a2a"]["_instance"].start_server(host, port)
