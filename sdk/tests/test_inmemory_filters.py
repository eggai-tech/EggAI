"""Broker-independent tests for InMemoryTransport filtering / typed subscriptions.

The existing `test_inmemory_transport.py` is a runnable demo (no test functions),
and the filter/data_type scenarios elsewhere use KafkaTransport — so they are
skipped when no broker is available. That left InMemory's filtering untested,
which is how its data_type-presence bugs went unnoticed. These tests run with no
broker and assert InMemory shares the same filtering contract as Redis/Kafka
(both now go through wrap_handler_with_filters).
"""

import asyncio
import uuid

import pytest
from pydantic import BaseModel

from eggai import Agent, Channel
from eggai.schemas import BaseMessage
from eggai.transport import InMemoryTransport


class Order(BaseModel):
    order_id: int
    status: str


class OrderMessage(BaseMessage[Order]):
    type: str = "OrderMessage"


class PaymentMessage(BaseMessage[Order]):
    type: str = "PaymentMessage"


async def _collect(subscribe_kwargs, messages, *, settle=0.1):
    """Subscribe a handler on a fresh in-memory channel, publish messages, and
    return what the handler received."""
    transport = InMemoryTransport()
    agent = Agent(f"agent-{uuid.uuid4().hex[:8]}", transport=transport)
    channel = Channel(f"chan-{uuid.uuid4().hex[:8]}", transport=transport)

    received = []
    done = asyncio.Event()

    @agent.subscribe(channel=channel, **subscribe_kwargs)
    async def handler(message):
        received.append(message)
        done.set()

    await agent.start()
    for msg in messages:
        await channel.publish(msg)
    await asyncio.sleep(settle)
    await agent.stop()
    return received


@pytest.mark.asyncio
async def test_inmemory_filter_by_message_routes_dicts():
    received = await _collect(
        {"filter_by_message": lambda m: m.get("type") == "keep"},
        [{"type": "drop", "v": 1}, {"type": "keep", "v": 2}],
    )
    assert [m["type"] for m in received] == ["keep"]


@pytest.mark.asyncio
async def test_inmemory_data_type_delivers_typed_instance():
    received = await _collect(
        {"data_type": OrderMessage},
        [
            PaymentMessage(source="t", data=Order(order_id=1, status="x")),
            OrderMessage(source="t", data=Order(order_id=42, status="new")),
        ],
    )
    assert len(received) == 1
    assert isinstance(received[0], OrderMessage)  # typed, not dict
    assert received[0].data.order_id == 42


@pytest.mark.asyncio
async def test_inmemory_filter_by_data_narrows_typed():
    received = await _collect(
        {
            "data_type": OrderMessage,
            "filter_by_data": lambda o: o.data.status == "shipped",
        },
        [
            OrderMessage(source="t", data=Order(order_id=1, status="new")),
            OrderMessage(source="t", data=Order(order_id=2, status="shipped")),
        ],
    )
    assert [o.data.order_id for o in received] == [2]


@pytest.mark.asyncio
async def test_inmemory_data_type_none_with_filter_by_message_filters_raw():
    """P2: data_type=None must behave like 'no data_type' — raw filtering works,
    not a raised error or a skip-everything typed branch."""
    received = await _collect(
        {"data_type": None, "filter_by_message": lambda m: m.get("keep") is True},
        [{"keep": False}, {"keep": True}],
    )
    assert received == [{"keep": True}]


@pytest.mark.asyncio
async def test_inmemory_data_type_none_alone_delivers_all():
    """P2: data_type=None alone must not enter the typed branch and silently skip
    every message."""
    received = await _collect({"data_type": None}, [{"a": 1}, {"a": 2}])
    assert received == [{"a": 1}, {"a": 2}]


@pytest.mark.asyncio
async def test_inmemory_rejects_invalid_filter_combinations():
    transport = InMemoryTransport()

    async def handler(m):
        return m

    with pytest.raises(ValueError, match="cannot be combined with data_type"):
        await transport.subscribe(
            "c", handler, data_type=OrderMessage, filter_by_message=lambda m: True
        )

    with pytest.raises(ValueError, match="filter_by_data requires data_type"):
        await transport.subscribe("c", handler, filter_by_data=lambda o: True)

    # P3: the missing-'type'-field validation now applies to InMemory too (it
    # goes through the same shared wrapper), instead of a delivery-time KeyError.
    class NoType(BaseModel):
        value: int

    with pytest.raises(ValueError, match="must define a 'type' field"):
        await transport.subscribe("c", handler, data_type=NoType)
