import asyncio

import pytest

from eggai import Agent, Channel
from eggai.transport import InMemoryTransport, eggai_set_default_transport

eggai_set_default_transport(lambda: InMemoryTransport())

hits = {}

def hit(key):
    hits[key] = hits.get(key, 0) + 1

@pytest.mark.asyncio
async def test_kafka(capfd):
    agent = Agent("OrderAgent")
    default_channel = Channel()

    @agent.subscribe(filter_by_message=lambda msg: msg.get("type") == "order_requested")
    async def handle_order_requested(msg):
        hit("order_requested")
        await default_channel.publish({
            "type": "order_created"
        })

    @agent.subscribe(filter_by_message=lambda msg: msg.get("type") == "order_created")
    async def handle_order_created(msg):
        hit("order_created")

    await agent.start()

    await default_channel.publish({
        "type": "order_requested"
    })
    await asyncio.sleep(0.5)
    assert hits.get("order_requested") == 1
    assert hits.get("order_created") == 1

    await agent.stop()
    await default_channel.stop()


@pytest.mark.asyncio
async def test_channel_subscribe_multiple():
    channel1 = Channel(name="test_channel")
    channel2 = Channel(name="test_channel")
    other_channel = Channel(name="other_channel")

    received_test_channel = []
    received_other_channel = []

    await channel1.subscribe(lambda event: received_test_channel.append(("channel1", event)))
    await channel2.subscribe(lambda event: received_test_channel.append(("channel2", event)))
    await other_channel.subscribe(lambda event: received_other_channel.append(event))

    await channel1.publish({"event": "test_event", "value": 1})
    await asyncio.sleep(0.5)
    assert len(received_test_channel) == 2, (
        f"Expected 2 events for 'test_channel', got {len(received_test_channel)}"
    )

    await other_channel.publish({"event": "other_event", "value": 2})
    await asyncio.sleep(0.5)
    assert len(received_other_channel) == 1, (
        f"Expected 1 event for 'other_channel', got {len(received_other_channel)}"
    )

    await channel1.stop()
    await channel2.stop()
    await other_channel.stop()
