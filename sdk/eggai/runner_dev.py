import asyncio

from eggai import Agent, Channel, KafkaTransport

transport = KafkaTransport()

agent = Agent("Agent1", transport=transport)
channel = Channel(transport=transport)
channel2 = Channel(transport=transport)


@agent.subscribe(channel=channel)
async def log_all(event):
    print(f"Type={event['type']}, Payload={event['payload']}")

async def run_test_scenario():
    await agent.run()

    await channel.publish({
        "type": "channel-1",
        "payload": 0
    })
    print("Published to channel 1")

    await channel2.publish({
        "type": "channel-2",
        "payload": 1
    })
    print("Published to channel 2")

    try:
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await channel.stop()
        await channel2.stop()
        await agent.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_test_scenario())
    except KeyboardInterrupt:
        print("User interrupted. Cleaning up...")


