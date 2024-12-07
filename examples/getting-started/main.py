import asyncio

from eggai import Channel
from email_agent import agent as email_agent
from order_agent import agent as order_agent


async def main():
    channel = Channel()

    await order_agent.run()
    await email_agent.run()

    await channel.publish({
        "event_name": "order_requested",
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
        await channel.stop()


if __name__ == "__main__":
    asyncio.run(main())
