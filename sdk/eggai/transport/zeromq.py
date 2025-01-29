import asyncio
import json
import platform
from typing import Callable, Set, Dict, Any, Awaitable

import zmq
import zmq.asyncio

from .base import BaseTransport


class ZeroMQTransport(BaseTransport):
    """
    A ZeroMQ transport using a single PUB/SUB socket pair.
    - PUB socket binds to a single TCP port for all channels.
    - SUB socket subscribes to specific channels via topic filtering.
    - Channel name is sent as the first message frame (topic).
    """

    _transports: Dict[str, "ZeroMQTransport"] = {}

    def __new__(
            cls,
            host: str = "127.0.0.1",
            start_port: int = 5560
    ):
        if platform.system() == "Windows":
            from asyncio import WindowsSelectorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

        if f"{host}:{start_port}" in cls._transports:
            return cls._transports[f"{host}:{start_port}"]

        instance = super().__new__(cls)
        cls._transports[f"{host}:{start_port}"] = instance
        return instance

    def __init__(self, host: str = "127.0.0.1", start_port: int = 5560):

        if not hasattr(self, "_initialized"):
            self.host = host
            self.start_port = start_port
            self._ctx = zmq.asyncio.Context()
            self._pub_socket: zmq.asyncio.Socket = None
            self._sub_socket: zmq.asyncio.Socket = None
            self._running = False
            self._consume_task: asyncio.Task = None
            self._initialized = True

    async def start(self, channels: Set[str], group_id: str = ""):
        """Initialize sockets with proper connection order."""
        if self._running:
            return

        pub_address = f"tcp://{self.host}:{self.start_port}"

        self._sub_socket = self._ctx.socket(zmq.SUB)
        self._sub_socket.setsockopt(zmq.LINGER, 0)
        self._sub_socket.bind(pub_address)

        for channel in channels:
            self._sub_socket.setsockopt(zmq.SUBSCRIBE, channel.encode())

        self._pub_socket = self._ctx.socket(zmq.PUB)
        self._pub_socket.setsockopt(zmq.LINGER, 0)
        self._pub_socket.connect(pub_address)

        self._running = True

    async def stop(self):
        """Cleanly shutdown sockets and context."""
        self._running = False

        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass

        if self._pub_socket:
            self._pub_socket.close()
        if self._sub_socket:
            self._sub_socket.close()
        self._ctx.term()

    async def produce(self, channel: str, message: Dict[str, Any]):
        """Send message with channel as topic frame."""
        if not self._pub_socket:
            raise RuntimeError("Transport not started. Call start() first.")

        await self._pub_socket.send_multipart([
            channel.encode(),
            json.dumps(message).encode("utf-8")
        ])

    async def consume(self, on_message: Callable[[str, Dict[str, Any]], Awaitable]):
        """Start consuming messages with channel-based filtering."""
        if not self._running:
            raise RuntimeError("Transport not started. Call start() first.")

        self._consume_task = asyncio.create_task(self._consume_loop(on_message))

    async def _consume_loop(self, on_message: Callable[[str, Dict[str, Any]], Awaitable]):
        """Improved consumption loop with direct recv."""
        while self._running:
            try:
                topic, payload = await self._sub_socket.recv_multipart()
                await on_message(topic.decode(), json.loads(payload.decode("utf-8")))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Consume error: {str(e)}")
