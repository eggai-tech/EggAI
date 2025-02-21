import asyncio

import pytest

from eggai import Agent, Channel, eggai_cleanup

agent = Agent("OrderAgent")
channel = Channel()

hits = {}


def hit(key):
    hits[key] = hits.get(key, 0) + 1

@agent.subscribe(filter_func=lambda e: e.get("type") == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event['payload']}")
    hit("order_requested")
    await channel.publish({"type": "order_created", "payload": event["payload"]})


@agent.subscribe(filter_func=lambda e: e.get("type") == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event['payload']}")
    hit("order_created")

@pytest.mark.asyncio
async def test_simple_scenario(capfd):
    await agent.start()

    await channel.publish({
        "type": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })

    await asyncio.sleep(2)

    await channel.publish({
        "type": "order_requested",
        "payload": {
            "product": "Mouse",
            "quantity": 2
        }
    })

    await asyncio.sleep(5)

    captured = capfd.readouterr()
    stdout = captured.out
    assert "[ORDER AGENT]: Received order request. Event:" in stdout
    assert "[ORDER AGENT]: Order created. Event:" in stdout
    assert "Mouse" in stdout
    assert "Laptop" in stdout

    assert hits.get("order_requested") == 2
    assert hits.get("order_created") == 2

    await eggai_cleanup()
