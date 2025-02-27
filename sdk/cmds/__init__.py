import asyncio

from eggai import Agent, Channel
from eggai.hooks import eggai_cleanup
from eggai.transport import KafkaTransport, eggai_set_default_transport

# Set KafkaTransport as the default transport.
eggai_set_default_transport(lambda: KafkaTransport())

# Global dictionary to track hits.
hits = {}

def hit(key):
    hits[key] = hits.get(key, 0) + 1
    print(f"Hit: {key} -> {hits[key]}")


default_channel = Channel()

async def test_group_ids():
    hits.clear()
    agent = Agent("SingleAgent")

    @agent.subscribe(
        filter_func=lambda event: event["type"] == 1,
        group_id="group_A"
    )
    async def handler_group_A(event):
        hit("group_A")

    @agent.subscribe(
        filter_func=lambda event: event["type"] == 1,
        group_id="group_B"
    )
    async def handler_group_B(event):
        hit("group_B")

    await agent.start()
    await default_channel.publish({"type": 1})
    await asyncio.sleep(2)

    # Since the subscriptions are in different groups, both should get the message.
    if hits.get("group_A") != 1:
        print(f"Expected group_A handler to be triggered once, but got {hits.get('group_A')}")
    
    if hits.get("group_B") != 1:
        print(f"Expected group_B handler to be triggered once, but got {hits.get('group_B')}")
    
    
        
async def test_group_ids_2():
    hits.clear()
    transport_process_1 = KafkaTransport(
        max_records_per_batch=5
    )
    agent1 = Agent("Agent1", transport=transport_process_1)
    
    transport_process_2 = KafkaTransport(
        max_records_per_batch=5
    )
    agent2 = Agent("Agent2", transport=transport_process_2)

    @agent1.subscribe(
        filter_func=lambda event: event["type"] == 2,
        group_id="group_C"
    )
    async def handler_agent1(event):
        hit("group_C")

    @agent2.subscribe(
        filter_func=lambda event: event["type"] == 2,
        group_id="group_C"
    )
    async def handler_agent2(event):
        hit("group_C")

    print("Starting agent 1")
    await agent1.start()
    
    print("Publishing event block #1")
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    
    print("Starting agent 2")
    await agent2.start()
    
    print("Publishing event block #2")
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    await default_channel.publish({"type": 2})
    
    print("Sleeping for 1 second")
    await asyncio.sleep(3)

    # With both agents in the same consumer group for type 2 events, only one should process the event.
    if hits.get("group_C") != 20:
        print(f"Expected group_C handler to be triggered once, but got {hits.get('group_C')}")
        
    await eggai_cleanup()

if __name__ == "__main__":
    asyncio.run(test_group_ids_2())