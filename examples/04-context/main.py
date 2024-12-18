import asyncio

from eggai import Channel

from agents.audit_agent import audit_agent
from channels import agents_channel
from agents.human_agent import human_agent
from agents.products_agent import products_agent
from agents.recommendation_agent import recommendation_agent


async def main():
    await human_agent.run()
    await audit_agent.run()
    await products_agent.run()
    await recommendation_agent.run()

    await agents_channel.publish({
        "message_id": "ID-0",
        "event": "user_query",
        "payload": "Can you recommend a smartphone, i like gaming on it. I prefer Apple if possible"
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await recommendation_agent.stop()
        await products_agent.stop()
        await human_agent.stop()
        await audit_agent.stop()
        await Channel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")