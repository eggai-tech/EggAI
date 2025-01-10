import asyncio

from sdk.eggai import Channel
from email_agent import agent as email_agent


async def main():
    channel = Channel()

    await email_agent.run()

    await channel.publish({
        "event_name": "email_prompt_requested",
        "payload": {
            "prompt": "how many emails did i get in the last 5 days?"
        }
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await email_agent.stop()
        await channel.stop()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
