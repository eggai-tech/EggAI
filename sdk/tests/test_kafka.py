import asyncio

import pytest

from eggai import Agent, Channel

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event['payload']}")
    await channel.publish({"event_name": "order_created", "payload": event["payload"]})


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event['payload']}")


async def run_test_scenario():
    await agent.run()
    await channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })
    await asyncio.sleep(2)
    await channel.stop()
    await agent.stop()


@pytest.mark.asyncio
async def test_events(capfd):
    # Run the scenario
    await run_test_scenario()

    # Capture output
    captured = capfd.readouterr()
    stdout = captured.out

    # Check if the agent printed the expected lines
    assert "[ORDER AGENT]: Received order request. Event:" in stdout
    assert "[ORDER AGENT]: Order created. Event:" in stdout
    # Optionally, you could check for expected payload data in the outpgit ut
    assert "Laptop" in stdout
    assert "quantity" in stdout
