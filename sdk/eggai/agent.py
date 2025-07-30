import asyncio
from collections import defaultdict
from typing import (
    List, Dict, Any, Optional, Callable, Tuple, Type, TypeVar, Awaitable
)

from .channel import Channel
from .hooks import eggai_register_stop
from .schemas import BaseMessage
from .transport import get_default_transport
from .transport.base import Transport

HANDLERS_IDS = defaultdict(int)

T = TypeVar('T')

class Agent:
    """
    A message-based agent for subscribing to events and handling messages
    with user-defined functions.
    """

    def __init__(self, name: str, transport: Optional[Transport] = None):
        """
        Initializes the Agent instance.

        Args:
            name (str): The name of the agent (used as an identifier).
            transport (Optional[Transport]): A concrete transport instance (e.g., KafkaTransport, InMemoryTransport).
                If None, defaults to InMemoryTransport.
        """
        self._name = name
        self._transport = transport
        self._subscriptions: List[Tuple[str, Callable[[Dict[str, Any]], "asyncio.Future"], Dict]] = []
        self._started = False
        self._stop_registered = False

    def _get_transport(self):
        if self._transport is None:
            self._transport = get_default_transport()
        return self._transport

    def subscribe(self, channel: Optional[Channel] = None, **kwargs):
        """
        Decorator for adding a subscription.

        Args:
            channel (Optional[Channel]): The channel to subscribe to. If None, defaults to "eggai.channel".

        Returns:
            Callable: A decorator that registers the given handler for the subscription.
        """

        def decorator(handler: Callable[[Dict[str, Any]], "asyncio.Future"]):
            channel_name = channel.get_name() if channel else "eggai.channel"
            self._subscriptions.append((channel_name, handler, kwargs))
            return handler

        return decorator

    async def to_a2a(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Expose this agent via HTTP API for agent-to-agent communication.
        
        Args:
            host (str): Host to bind the server to. Defaults to "0.0.0.0".
            port (int): Port to bind the server to. Defaults to 8080.
            
        Returns:
            A2AServer: The running A2A server instance.
            
        Raises:
            ImportError: If FastAPI/uvicorn dependencies are not installed.
        """
        try:
            from .a2a.server import A2AServer
        except ImportError as e:
            raise ImportError(
                "A2A functionality requires additional dependencies. "
                "Install with: pip install fastapi uvicorn httpx"
            ) from e
        
        server = A2AServer(self, host=host, port=port)
        return await server.start()

    async def start(self):
        """
        Starts the agent by connecting the transport and subscribing to all registered channels.

        If no transport is provided, a default transport is used. Also registers a stop hook if not already registered.
        """
        if self._started:
            return

        for (channel, handler, kwargs) in self._subscriptions:
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
