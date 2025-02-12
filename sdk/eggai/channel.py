import asyncio
from typing import Dict, Any, Optional, Callable, List, Tuple
from .hooks import eggai_register_stop
from .transport.base import Transport, get_default_transport


class Channel:
    """
    A channel that publishes messages to a given 'name' on its own Transport.
    Default name is "eggai.channel".
    Lazy connection on first publish, or start() if you subscribe.
    """

    def __init__(self, name: str = "eggai.channel", transport: Optional[Transport] = None):
        """
        :param name: Channel (topic) name.
        :param transport: A concrete transport instance. If None, defaults will be used.
        """
        self._name = name
        self._transport = transport
        self._sub_connected = False
        self._stop_registered = False
        self._subscriptions: List[Tuple[int, Callable[[Dict[str, Any]], bool], Callable]] = []
        self._listening = False
        self._subscription_id = 1000

    async def _ensure_connected(self):
        """
        Ensures that a connection is established for either publishing or subscribing.
        """
        if not self._sub_connected:
            if self._transport is None:
                self._transport = get_default_transport()
            await self._transport.connect(group_id=self._name)
            self._sub_connected = True
            if not self._stop_registered:
                await eggai_register_stop(self.stop)
                self._stop_registered = True

    async def publish(self, message: Dict[str, Any]):
        """
        Publish a message to the channel.
        """
        await self._ensure_connected()
        await self._transport.publish(self._name, message)

    def subscribe(self, handler: Callable[[Dict[str, Any]], "asyncio.Future"], filter_func: Callable[[Dict[str, Any]], bool] = lambda e: True):
        subscription_id = self._subscription_id + 1
        def unsubscribe():
            self.unsubscribe(subscription_id)
        self._subscriptions.append((subscription_id, filter_func, handler))
        self._subscription_id = subscription_id
        return unsubscribe, subscription_id


    def unsubscribe(self, subscription_id: int):
        """
        Unsubscribe from the channel.
        """
        self._subscriptions = [(sid, ff, h) for sid, ff, h in self._subscriptions if sid != subscription_id]


    async def start(self):
        """
        Start listening for messages on this channel and dispatch them to subscribed handlers.
        """
        if self._listening:
            return

        await self._ensure_connected()

        async def aggregator(msg: Dict[str, Any]):
            for _, filter_func, handler_func in self._subscriptions:
                if filter_func(msg):
                    if asyncio.iscoroutinefunction(handler_func):
                        await handler_func(msg)
                    else:
                        handler_func(msg)

        await self._transport.subscribe(self._name, aggregator)
        self._listening = True

    async def stop(self):
        """
        Disconnect the channel's transport if connected.
        """
        if self._sub_connected:
            await self._transport.disconnect()
            self._sub_connected = False
