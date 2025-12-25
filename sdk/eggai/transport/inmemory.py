import asyncio
import json
import uuid
from collections import defaultdict
from typing import Dict, List, Callable, Tuple, Any, Union

from eggai.schemas import BaseMessage
from eggai.transport import Transport


class InMemoryTransport(Transport):
    """
    In-memory message transport for testing, prototyping, and local development.

    This transport implementation uses asyncio queues to handle message passing
    between agents within a single Python process. Messages are not persisted
    and will be lost if the process terminates.

    **Use Cases:**
    - Unit testing and integration tests
    - Local development and prototyping
    - Single-process multi-agent applications
    - Quick experimentation without external dependencies

    **NOT Recommended For:**
    - Production deployments
    - Multi-process or distributed systems
    - Applications requiring message persistence
    - Systems needing high availability

    **Features:**
    - Zero external dependencies (no Kafka, Redis, etc.)
    - Instant message delivery (no network latency)
    - Consumer group support for load balancing
    - Thread-safe within a single event loop

    **Example:**
    ```python
    from eggai import Agent, Channel, InMemoryTransport

    transport = InMemoryTransport()
    agent = Agent("my-agent", transport=transport)
    channel = Channel("my-channel", transport=transport)

    await transport.connect()
    await agent.start()
    ```

    Note: All InMemoryTransport instances share the same in-memory queues
    (class-level storage), allowing agents to communicate within the same process.
    """
    # One queue per (channel, group_id). Each consumer group gets its own queue.
    _CHANNELS: Dict[str, Dict[str, asyncio.Queue]] = defaultdict(dict)
    # For each channel and group_id, store a list of subscription callbacks.
    _SUBSCRIPTIONS: Dict[
        str, Dict[str, List[Callable[[Dict[str, Any]], "asyncio.Future"]]]
    ] = defaultdict(lambda: defaultdict(list))

    def __init__(self):
        self._connected = False
        # Keep references to consume tasks keyed by (channel, group_id)
        self._consume_tasks: Dict[Tuple[str, str], asyncio.Task] = {}

    async def connect(self):
        """Marks the transport as connected and starts consume loops for existing subscriptions."""
        self._connected = True
        for channel, group_map in InMemoryTransport._SUBSCRIPTIONS.items():
            for group_id in group_map.keys():
                key = (channel, group_id)
                if key not in self._consume_tasks:
                    self._consume_tasks[key] = asyncio.create_task(
                        self._consume_loop(channel, group_id)
                    )

    async def disconnect(self):
        """Cancels all consume loops and marks the transport as disconnected."""
        for task in self._consume_tasks.values():
            task.cancel()
        for task in self._consume_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consume_tasks.clear()
        self._connected = False

    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
        """
        Publishes a message to the given channel.
        The message is put into all queues for that channel so each consumer group receives it.
        """
        if not self._connected:
            raise RuntimeError("Transport not connected. Call `connect()` first.")
        if channel not in InMemoryTransport._CHANNELS:
            InMemoryTransport._CHANNELS[channel] = {}

        if hasattr(message, "model_dump_json"):
            data = message.model_dump_json()
        else:
            data = json.dumps(message)

        for grp_id, queue in InMemoryTransport._CHANNELS[channel].items():
            await queue.put(data)

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Dict[str, Any]], "asyncio.Future"],
        **kwargs,
    ):
        """
        Subscribes to a channel with the provided group_id.
        If no group_id is given, a unique one is generated, ensuring that each subscription
        gets its own consumer (broadcast mode).
        """
        handler_id = kwargs.pop("handler_id", None)
        group_id = kwargs.get("group_id", handler_id or uuid.uuid4().hex)
        key = (channel, group_id)

        final_callback = callback

        # Handle data_type filtering
        if "data_type" in kwargs:
            data_type = kwargs["data_type"]

            async def data_type_filtered_callback(data):
                try:
                    typed_message = data_type.model_validate(data)
                    # Check if message type matches expected type
                    if typed_message.type != data_type.model_fields["type"].default:
                        return
                    # Pass the typed message object to the handler
                    await callback(typed_message)
                except Exception:
                    # Skip messages that don't match the data type
                    return

            final_callback = data_type_filtered_callback

            # Handle filter_by_data if present along with data_type
            if "filter_by_data" in kwargs:
                filter_func = kwargs["filter_by_data"]

                async def data_and_filter_callback(data):
                    try:
                        typed_message = data_type.model_validate(data)
                        # Check if message type matches expected type
                        if typed_message.type != data_type.model_fields["type"].default:
                            return
                        # Apply the data filter
                        if filter_func(typed_message):
                            await callback(typed_message)
                    except Exception:
                        # Skip messages that don't match the data type or filter
                        return

                final_callback = data_and_filter_callback

        # Handle legacy filter_by_message (for backward compatibility)
        elif "filter_by_message" in kwargs:
            filter_func = kwargs["filter_by_message"]

            async def filtered_callback(data):
                if filter_func(data):
                    await final_callback(data)

            final_callback = filtered_callback

        InMemoryTransport._SUBSCRIPTIONS[channel][group_id].append(final_callback)

        if group_id not in InMemoryTransport._CHANNELS[channel]:
            InMemoryTransport._CHANNELS[channel][group_id] = asyncio.Queue()
        if self._connected and key not in self._consume_tasks:
            self._consume_tasks[key] = asyncio.create_task(
                self._consume_loop(channel, group_id)
            )

    async def _consume_loop(self, channel: str, group_id: str):
        """
        Continuously pulls messages from the queue for (channel, group_id)
        and dispatches them to all registered callbacks.
        """
        queue = InMemoryTransport._CHANNELS[channel].get(group_id)
        if not queue:
            queue = asyncio.Queue()
            InMemoryTransport._CHANNELS[channel][group_id] = queue

        try:
            while True:
                msg = await queue.get()
                data = json.loads(msg)
                callbacks = InMemoryTransport._SUBSCRIPTIONS[channel].get(group_id, [])
                for cb in callbacks:
                    await cb(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(
                f"InMemoryTransport consume loop error on channel={channel}, group={group_id}: {e}"
            )
