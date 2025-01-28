import asyncio
import json
import platform
from typing import Callable, Set, Dict, Any, Awaitable

import zmq
import zmq.asyncio

from .base import BaseTransport

class ZeroMQTransport(BaseTransport):
    """
    A naive ZeroMQ transport that:
      - Creates a PULL socket for each channel (bound to an incremental TCP port).
      - Creates a PUSH socket for each channel (connected to that port).
      - Uses PUSH/PULL to ensure messages on each channel are load-balanced
        across consumers (only one consumer gets a given message).

    NOTE: This implementation is simplified for demonstration:
      - All channels are 'started' in one call, each binding a unique port.
      - We store those ports in-memory. For real multi-machine use,
        you typically have one 'server' side that binds and multiple
        producers connect from elsewhere.
    """

    # create a static field to hold the all the bindings
    _bindings = {}

    def __init__(self, host: str = "127.0.0.1", start_port: int = 5560):
        """
        :param host: IP/Hostname where PULL sockets will bind.
        :param start_port: The first TCP port to bind for the first channel.
                           Additional channels increment the port by 1, etc.
        """

        # check if is running on windows, set asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
        if platform.system() == "Windows":
            from asyncio import WindowsSelectorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

        self.host = host
        self.start_port = start_port

        self._ctx = zmq.asyncio.Context()
        self._pull_sockets: Dict[str, zmq.asyncio.Socket] = {}   # channel -> PULL socket
        self._push_sockets: Dict[str, zmq.asyncio.Socket] = {}   # channel -> PUSH socket
        self._ports: Dict[str, int] = {}                         # channel -> assigned port

        self._running = False
        self._consume_task: asyncio.Task = None

    async def start(self, channels: Set[str], group_id: str = ""):
        """
        Initialize PULL and PUSH sockets for each channel, binding them
        to incremental TCP ports on self.host.
        """
        current_port = self.start_port
        for channel in channels:
            # Create a PULL socket, bind it to tcp://host:port
            bind_address = f"tcp://{self.host}:{current_port}"

            if bind_address not in ZeroMQTransport._bindings:
                pull_sock = self._ctx.socket(zmq.PULL)
                ZeroMQTransport._bindings[channel] = bind_address
                pull_sock.bind(bind_address)
                self._pull_sockets[channel] = pull_sock
                ZeroMQTransport._bindings[bind_address] = pull_sock

            # Create a PUSH socket, connect it to the same address
            push_sock = self._ctx.socket(zmq.PUSH)
            push_sock.connect(bind_address)

            self._push_sockets[channel] = push_sock
            self._ports[channel] = current_port

            current_port += 1

        self._running = True

    async def stop(self):
        """
        Stop the transport by cancelling the consume task
        and closing all sockets.
        """
        self._running = False
        if self._consume_task is not None:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        # Close sockets
        for sock in self._pull_sockets.values():
            sock.close()
            for key, value in ZeroMQTransport._bindings.items():
                if value == sock:
                    ZeroMQTransport._bindings[key] = None

            ZeroMQTransport._bindings = {k: v for k, v in ZeroMQTransport._bindings.items() if v is not None}

        for sock in self._push_sockets.values():
            sock.close()
        self._pull_sockets.clear()
        self._push_sockets.clear()
        self._ports.clear()

        self._ctx.term()

    async def produce(self, channel: str, message: Dict[str, Any]):
        """
        Send (produce) a JSON-encoded message to the push socket
        for the specified channel.
        """
        if channel not in self._push_sockets:
            raise RuntimeError(f"Channel '{channel}' not started in ZeroMQTransport.")
        data = json.dumps(message).encode("utf-8")
        await self._push_sockets[channel].send(data)

    async def consume(self, on_message: Callable[[str, Dict[str, Any]], None]):
        """
        Continuously poll all pull sockets and invoke on_message(channel, message_dict).

        This method spawns a background task that loops until stop() is called.
        """
        if not self._running:
            raise RuntimeError("Transport not started. Call 'start()' before 'consume()'.")

        self._consume_task = asyncio.create_task(self._consume_loop(on_message))

    async def _consume_loop(self, on_message: Callable[[str, Dict[str, Any]], Awaitable]):
        poller = zmq.asyncio.Poller()
        for channel, pull_sock in self._pull_sockets.items():
            poller.register(pull_sock, zmq.POLLIN)

        while self._running:
            events = dict(await poller.poll(timeout=1000))
            for channel, pull_sock in self._pull_sockets.items():
                if pull_sock in events and events[pull_sock] == zmq.POLLIN:
                    raw_data = await pull_sock.recv()
                    msg_dict = json.loads(raw_data.decode("utf-8"))
                    await on_message(channel, msg_dict)
