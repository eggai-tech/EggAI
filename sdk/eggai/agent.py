from typing import Optional, Callable, Dict, Any
from .channel import Channel
from .hooks import eggai_register_stop


class Agent:
    """
    A message-based agent that orchestrates channels.
    Channels manage their own transport connections.
    """

    def __init__(self, name: str):
        """
        :param name: The name of the agent (used as a consumer group ID for subscriptions).
        """
        self._name = name
        self._channels: list[Channel] = []
        self._default_channel: Optional[Channel] = None
        self._started = False
        self._stop_registered = False

    def add_channel(self, channel: Channel):
        """
        Register a channel with this agent.
        """
        if channel not in self._channels:
            self._channels.append(channel)

    def subscribe(
            self,
            channel: Optional[Channel] = None,
            filter_func: Callable[[Dict[str, Any]], bool] = lambda e: True
    ):
        """
        A decorator that registers a subscription for an event.
        Internally, it uses the channel's subscribe method.

        If no channel is provided, a default channel (with name "eggai.channel")
        is created (or reused if already created) and added to the agent.

        Example:

            @agent.subscribe(filter_func=lambda e: e.get("type") == "greeting")
            async def handle_greeting(event):
                print("Got greeting:", event)
        """
        if channel is None:
            if self._default_channel is None:
                self._default_channel = Channel()  # defaults to "eggai.channel"
                self.add_channel(self._default_channel)
            channel = self._default_channel
        else:
            self.add_channel(channel)
        def decorator(handler):
            channel.subscribe(handler, filter_func)
            return handler
        return decorator

    async def start(self):
        """
        Start all registered channels so they begin listening for events.
        Uses the agent's name as the group_id for subscriptions.
        """
        if self._started:
            return

        self._started = True

        if not self._stop_registered:
            await eggai_register_stop(self.stop)
            self._stop_registered = True

        # Start listening on each registered channel using the agent's name as the group_id.
        for channel in self._channels:
            await channel.start()

    async def stop(self):
        """
        Stop all channels managed by this agent.
        """
        if self._started:
            for channel in self._channels:
                await channel.stop()
            self._started = False
