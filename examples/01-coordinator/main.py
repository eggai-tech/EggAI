import asyncio

from eggai import Channel
from email_agent import agent as email_agent
from order_agent import agent as order_agent
from coordinator import agent as coordinator


async def main():
    human_channel = Channel("human")

    await coordinator.run()
    await order_agent.run()
    await email_agent.run()

    await human_channel.publish({
        "action": "create_order",
        "payload": {
            "product": "Laptop", "quantity": 1
        }
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await order_agent.stop()
        await email_agent.stop()
        await coordinator.stop()
        await Channel.stop()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
