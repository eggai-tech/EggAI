import asyncio

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport

eggai_set_default_transport(lambda: KafkaTransport())

@pytest.mark.asyncio
async def test_kafka(capfd):
    agent = Agent("OrderAgent")
    default_channel = Channel()

    @agent.subscribe(filter_func=lambda event: event["event_name"] == "order_requested")
    async def handle_order_requested(event):
        print(f"[ORDER AGENT]: Received order request. Event: {event['payload']}")
        await default_channel.publish({
            "event_name": "order_created",
            "payload": event["payload"]
        })

    @agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
    async def handle_order_created(event):
        print(f"[ORDER AGENT]: Order created. Event: {event['payload']}")

    await agent.start()
    await default_channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })
    await asyncio.sleep(2)

    captured = capfd.readouterr()
    stdout = captured.out
    assert "[ORDER AGENT]: Received order request. Event:" in stdout
    assert "[ORDER AGENT]: Order created. Event:" in stdout
    assert "Laptop" in stdout
    assert "quantity" in stdout


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
    await asyncio.sleep(2)
    assert len(received_test_channel) == 2, (
        f"Expected 2 events for 'test_channel', got {len(received_test_channel)}"
    )

    await other_channel.publish({"event": "other_event", "value": 2})
    await asyncio.sleep(2)
    assert len(received_other_channel) == 1, (
        f"Expected 1 event for 'other_channel', got {len(received_other_channel)}"
    )
