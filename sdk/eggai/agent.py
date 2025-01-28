import asyncio
from collections import defaultdict
from typing import Dict, List, Callable, Optional, Type

from eggai.channel import Channel
from eggai.constants import DEFAULT_CHANNEL_NAME
from eggai.schemas import MessageBase
from eggai.transport.base import BaseTransport
from eggai.transport.zeromq import ZeroMQTransport


def _get_channel_name(channel: Optional[Channel], channel_name: Optional[str]) -> str:
    return channel.name if channel else channel_name or DEFAULT_CHANNEL_NAME


class Agent:
    """
    A message-based agent for subscribing to events and handling messages
    with user-defined functions.
    """

    def __init__(
            self,
            name: str,
            transport: BaseTransport = None,
    ):
        """
        :param name: The name of the agent (used as an identifier).
        :param transport: A concrete transport instance (KafkaTransport, ZeroMQTransport, etc.).
                          If None, defaults to KafkaTransport with the given kafka_settings.
        """
        self.name = name
        self.transport = transport or ZeroMQTransport()
        self._handlers: List[Dict] = []
        self._channels = set()
        self._running_task = None
        self._running = False

    def subscribe(
            self,
            channel_name: str = DEFAULT_CHANNEL_NAME,
            channel: Channel = None,
            filter_func: Optional[Callable[[Dict], bool]] = None,
            message_type: Type[MessageBase] = None
    ) -> Callable:
        def decorator(func: Callable):
            channel_name_to_use = _get_channel_name(channel, channel_name)
            self._handlers.append({
                "channel": channel_name_to_use,
                "filter": filter_func,
                "handler": func,
                "handler_name": func.__name__,
                "message_type": message_type
            })
            self._channels.add(channel_name_to_use)
            return func

        return decorator

    async def _handle_incoming_message(self, channel_name: str, message: dict):
        """
        Called by the transport layer whenever a new message arrives.
        We then dispatch to the appropriate handlers.
        """
        for handler_entry in self._handlers:
            if handler_entry["channel"] == channel_name:
                filter_func = handler_entry["filter"]
                handler = handler_entry["handler"]
                message_type = handler_entry["message_type"]
                safe_message = defaultdict(lambda: None, message)
                try:
                    if filter_func is None or filter_func(safe_message):
                        if message_type is not None:
                            safe_message = message_type(**message)
                        await handler(safe_message)
                except Exception as e:
                    print(
                        f"Failed to process message from {channel_name}: "
                        f"{e} {message} {self.name}.{handler_entry['handler_name']} {handler_entry['channel']}"
                    )

    async def _consume_loop(self):
        """
        This will be the task we run to continuously consume messages from the transport.
        """
        await self.transport.consume(self._handle_incoming_message)

    async def run(self):
        """
        Start the agent by initializing the transport and begin handling messages.
        """
        if self._running:
            raise RuntimeError("Agent is already running.")

        # Start the transport with the given channels
        await self.transport.start(channels=self._channels, group_id=f"{self.name}_group")
        self._running_task = asyncio.create_task(self._consume_loop())
        await asyncio.sleep(0.1)
        self._running = True

    async def stop(self):
        """
        Stop the agent gracefully by cancelling the running task and stopping the transport.
        """
        if not self._running:
            raise RuntimeError("Agent is not running.")

        if self._running_task:
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
            self._running_task = None

        await self.transport.stop()
        self._running = False
