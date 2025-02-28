import asyncio
import sys

from .configuration import PROCESSING_GUARANTEE
from eggai import Agent, Channel
from eggai.hooks import eggai_main
from eggai.transport import KafkaTransport

current_worker = sys.argv[1]

transport_process_1 = KafkaTransport(max_records_per_batch=5, processing_guarantee=PROCESSING_GUARANTEE)
agent1 = Agent("Agent1", transport=transport_process_1)
default_channel = Channel(transport=transport_process_1)

hits = 0

@agent1.subscribe(channel=default_channel, filter_func=lambda msg: msg["type"] == 2, group_id="group_C")
async def handler_agent1(msg):
    global hits
    print(f"{current_worker} - Agent1 - group_C - id: {msg['id']}")
    hits += 1
    print(f" ================= Hit: group_C -> {hits} from Agent1 with id {current_worker}")


@agent1.subscribe(channel=default_channel, filter_func=lambda msg: msg["type"] == 2, group_id="group_D")
async def handler_agent1(msg):
    print(f"{current_worker} - Agent1 - group_D - id: {msg['id']}")

@eggai_main
async def main():    
    await agent1.start()    
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())