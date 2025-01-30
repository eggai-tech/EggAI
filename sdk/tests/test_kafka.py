import asyncio

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport

kafka_transport = KafkaTransport()
agent = Agent("OrderAgent", transport=kafka_transport)
channel = Channel(transport=kafka_transport)


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event['payload']}")
    await channel.publish({"event_name": "order_created", "payload": event["payload"]})


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event['payload']}")


@pytest.mark.asyncio
async def test_kafka(capfd):
    eggai_set_default_transport(lambda: KafkaTransport())
    await agent.start()
    await channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })
    await asyncio.sleep(2)

    # Capture output
    captured = capfd.readouterr()
    stdout = captured.out

    # Check if the agent printed the expected lines
    assert "[ORDER AGENT]: Received order request. Event:" in stdout
    assert "[ORDER AGENT]: Order created. Event:" in stdout
    # Optionally, you could check for expected payload data in the output
    assert "Laptop" in stdout
    assert "quantity" in stdout
