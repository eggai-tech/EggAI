import asyncio

import pytest

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport, KafkaTransport

agent = Agent("OrderAgent")
channel = Channel()

hits = {}


def hit(key):
    hits[key] = hits.get(key, 0) + 1


@agent.subscribe(filter_func=lambda e: e.get("type") == "msg1")
async def handle_order_requested(event):
    hit("msg1")
    await channel.publish({"type": "msg2"})


@agent.subscribe(filter_func=lambda e: e.get("type") == "msg2")
async def handle_order_created(event):
    hit("msg2")


@pytest.mark.asyncio
async def test_simple_scenario(capfd):
    eggai_set_default_transport(lambda: KafkaTransport())

    await agent.start()
    await channel.publish({
        "type": "msg1"
    })
    await channel.publish({
        "type": "msg1"
    })
    await asyncio.sleep(0.5)
    assert hits.get("msg1") == 2
    assert hits.get("msg2") == 2
    await agent.stop()
