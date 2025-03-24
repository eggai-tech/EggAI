import asyncio
from collections import defaultdict

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport

eggai_set_default_transport(lambda: KafkaTransport())

hits = defaultdict(int)

@pytest.mark.asyncio
async def test_catch_all(capfd):
    agent = Agent("CatchAllTestAgent")
    channel = Channel("catch-all-tests")

    @agent.subscribe(
        channel,
        filter_by_message=lambda e: e.get("type") == "msg1"
    )
    async def handle_msg1(event):
        hits["msg1"] += 1
        await channel.publish({"type": "msg2"})

    await agent.start()
    await channel.publish({
        "type": "msg1"
    })
    await channel.publish({
        "type": "msg2"
    })
    await asyncio.sleep(0.5)
    await agent.stop()
    assert hits["msg1"] == 1
    # check no SubscriberNotFound exception is raised in the output of the test run
    captured = capfd.readouterr()
    assert "SubscriberNotFound" not in captured.out
