import asyncio

from eggai import Channel, eggai_cleanup
from eggai.schemas import Message

from email_agent import agent as email_agent
from order_agent import agent as order_agent


async def main():
    channel = Channel()

    await order_agent.start()
    await email_agent.start()

    await channel.publish(Message(
        type="order_requested",
        source="main",
        data={"product": "Laptop", "quantity": 1}
    ))

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    await eggai_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
