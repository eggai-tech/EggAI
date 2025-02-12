import asyncio

import pytest

from eggai import Agent, Channel, eggai_cleanup

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_func=lambda e: e.get("type") == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event['payload']}")
    await channel.publish({"type": "order_created", "payload": event["payload"]})


@agent.subscribe(filter_func=lambda e: e.get("type") == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event['payload']}")


@pytest.mark.asyncio
async def test_simple_scenario(capfd):
    unsub, sub_id = channel.subscribe(
        handler=lambda e: print("Received event from channel subscription: ", e),
        filter_func=lambda e: True
    )

    await channel.start()
    await agent.start()

    await channel.publish({
        "type": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })

    await asyncio.sleep(2)

    unsub()

    captured = capfd.readouterr()
    stdout = captured.out
    assert "[ORDER AGENT]: Received order request. Event:" in stdout
    assert "[ORDER AGENT]: Order created. Event:" in stdout
    assert "Received event from channel subscription:" in stdout
