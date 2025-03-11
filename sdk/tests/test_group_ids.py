import asyncio
import uuid

import pytest
from faststream.kafka import KafkaMessage

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport

eggai_set_default_transport(lambda: KafkaTransport())

hits = {}

def hit(key):
    hits[key] = hits.get(key, 0) + 1

@pytest.mark.asyncio
async def test_group_ids(capfd):
    default_channel = Channel()

    hits.clear()
    agent = Agent("SingleAgent")

    @agent.subscribe(
        filter_by_message=lambda event: event["type"] == 1,
        group_id="group_A"
    )
    async def handler_group_A(event):
        hit("group_A")

    @agent.subscribe(
        filter_by_message=lambda event: event["type"] == 1,
        group_id="group_B"
    )
    async def handler_group_B(event):
        hit("group_B")

    await agent.start()
    await default_channel.publish({"type": 1})
    await asyncio.sleep(0.5)

    # Since the subscriptions are in different groups, both should get the message.
    assert hits.get("group_A") == 1, "Expected group_A handler to be triggered once."
    assert hits.get("group_B") == 1, "Expected group_B handler to be triggered once."


@pytest.mark.asyncio
async def test_2_agents_same_group(capfd):
    hits.clear()
    default_channel = Channel()
    agent1 = Agent("Agent1")
    agent2 = Agent("Agent2")

    @agent1.subscribe(
        filter_by_message=lambda event: event["type"] == 2,
        group_id="group_C"
    )
    async def handler_agent1(event):
        hit("group_C")

    @agent2.subscribe(
        filter_by_message=lambda event: event["type"] == 2,
        group_id="group_C"
    )
    async def handler_agent2(event):
        hit("group_C")

    await agent1.start()
    await agent2.start()
    await default_channel.publish({"type": 2})
    await asyncio.sleep(2)

    # With both agents in the same consumer group for type 2 events, only one should process the event.
    assert hits.get("group_C") == 1, "Expected only one handler in group_C to be triggered due to consumer group load balancing."



@pytest.mark.asyncio
async def test_broadcasting(capfd):
    default_channel = Channel()
    hits.clear()

    agentA = Agent("AgentA")
    agentB = Agent("AgentB")

    @agentA.subscribe(
        filter_by_message=lambda event: event["type"] == 3
        # No group_id provided: broadcasting mode.
    )
    async def handler_agentA(event):
        hit("agentA")

    @agentB.subscribe(
        filter_by_message=lambda event: event["type"] == 3
        # No group_id provided: broadcasting mode.
    )
    async def handler_agentB(event):
        hit("agentB")

    await agentA.start()
    await agentB.start()
    await default_channel.publish({"type": 3})
    await asyncio.sleep(0.5)

    # Expect both agents to process the same broadcasted message.
    assert hits.get("agentA") == 1, "Expected AgentA to handle the broadcasted event."
    assert hits.get("agentB") == 1, "Expected AgentB to handle the broadcasted event."
