import asyncio

from eggai import Agent, Channel
from eggai.hooks import eggai_cleanup
from eggai.transport import KafkaTransport

from .configuration import PROCESSING_GUARANTEE

transport_process_1 = KafkaTransport(max_records_per_batch=5, processing_guarantee=PROCESSING_GUARANTEE)
default_channel = Channel(transport=transport_process_1)

async def main():
    for i in range(0, 10_000):
        await default_channel.publish({"type": 2, "id": i + 1})
    await eggai_cleanup()

if __name__ == "__main__":
    asyncio.run(main())