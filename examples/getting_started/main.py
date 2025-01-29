import asyncio

from eggai import Channel, eggai_stop

from email_agent import agent as email_agent
from order_agent import agent as order_agent


async def main():
    channel = Channel()

    await order_agent.start()
    await email_agent.start()

    await channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop", "quantity": 1
        }
    })

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    await eggai_stop()


if __name__ == "__main__":
    asyncio.run(main())
