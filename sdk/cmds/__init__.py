import asyncio

from eggai import Agent, Channel
from eggai.hooks import eggai_cleanup
from eggai.transport import KafkaTransport

hits = {}
end_reached_event = asyncio.Event()

async def handle_message(agent, group, event):
    extra = event.get("extra", "")
    current_id = event.get("id")
    if "delay" in extra:
        print(f"Delay start agent={agent}, for id = {current_id}")
        await asyncio.sleep(5)
        print(f"Delay end agent={agent}, for id = {current_id}")
    
    if "error" in extra:
        print(f"Error in agent={agent}, for id = {current_id}")
        raise Exception(f"Error in agent={agent}, for id = {current_id}")
    
    hits[group] = hits.get(group, 0) + 1
    print(f" ================= Hit: {group} -> {hits[group]} from {agent} with id {current_id}")
    
    if "end" in extra:
        end_reached_event.set()    

PROCESSING_GUARANTEE = "exactly_once"
PROCESSING_GUARANTEE = "at_least_once"

async def test_group_ids():
    hits.clear()
    
    transport_process_1 = KafkaTransport(max_records_per_batch=5, processing_guarantee=PROCESSING_GUARANTEE)
    
    default_channel = Channel(transport=transport_process_1)
    agent = Agent("SingleAgent", transport=transport_process_1)

    @agent.subscribe(channel=default_channel, filter_func=lambda msg: msg["type"] == 1, group_id="group_A")
    async def handler_group_A(msg):
        await handle_message("SingleAgent", "group_A", msg)

    @agent.subscribe(channel=default_channel, filter_func=lambda msg: msg["type"] == 1, group_id="group_B")
    async def handler_group_B(msg):
        await handle_message("SingleAgent", "group_B", msg)

    await agent.start()
    await default_channel.publish({"type": 1, "id": 1})
    
    await asyncio.sleep(2)

    if hits.get("group_A") != 1:
        print(f"Expected group_A handler to be triggered once, but got {hits.get('group_A')}")
    
    if hits.get("group_B") != 1:
        print(f"Expected group_B handler to be triggered once, but got {hits.get('group_B')}")

        
async def test_group_ids_2():
    hits.clear()
    
    transport_process_1 = KafkaTransport(max_records_per_batch=5, processing_guarantee=PROCESSING_GUARANTEE)
    agent1 = Agent("Agent1", transport=transport_process_1)
    default_channel = Channel(transport=transport_process_1)
    
    transport_process_2 = KafkaTransport(max_records_per_batch=1, processing_guarantee=PROCESSING_GUARANTEE)
    agent2 = Agent("Agent2", transport=transport_process_2)
    default_channel2 = Channel(transport=transport_process_2)

    @agent1.subscribe(channel=default_channel, filter_func=lambda msg: msg["type"] == 2, group_id="group_C")
    async def handler_agent1(msg):
        await handle_message("Agent1", "group_C", msg)

    @agent2.subscribe(channel=default_channel2, filter_func=lambda msg: msg["type"] == 2, group_id="group_C")
    async def handler_agent2(msg):
        await handle_message("Agent2", "group_C", msg)

    print("Starting agent 1")
    await agent1.start()
    
    print("Publishing event block #1")
    await default_channel.publish({"type": 2, "id": 1})
    await default_channel.publish({"type": 2, "id": 2})
    await default_channel.publish({"type": 2, "id": 3})
    await default_channel.publish({"type": 2, "id": 4})
    await default_channel.publish({"type": 2, "id": 5})
    await default_channel.publish({"type": 2, "id": 6})
    await default_channel.publish({"type": 2, "id": 7})
    await default_channel.publish({"type": 2, "id": 8, "extra": "error"})
    await default_channel.publish({"type": 2, "id": 9})
    await default_channel.publish({"type": 2, "id": 10, "extra": "delay,error"})

    print("Starting agent 2")
    await agent2.start()
    await agent1.stop()
    
    print("Publishing event block #2")
    await default_channel2.publish({"type": 2, "id": 11})
    await default_channel2.publish({"type": 2, "id": 12})
    await default_channel2.publish({"type": 2, "id": 13, "extra": "error"})
    await default_channel2.publish({"type": 2, "id": 14})
    await default_channel2.publish({"type": 2, "id": 15})
    await default_channel2.publish({"type": 2, "id": 16})
    await default_channel2.publish({"type": 2, "id": 17})
    await default_channel2.publish({"type": 2, "id": 18})
    await default_channel2.publish({"type": 2, "id": 19})
    await default_channel2.publish({"type": 2, "id": 20, "extra": "delay,end"})
    
    try:
        await asyncio.wait_for(end_reached_event.wait(), timeout=30)
    except asyncio.CancelledError:
        pass

    print(f"\n\n == Expected group_C is 20, but got {hits.get('group_C')} == \n\n")
    await eggai_cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(test_group_ids_2())
    except KeyboardInterrupt:
        print("Exiting...")