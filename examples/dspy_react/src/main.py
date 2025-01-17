import asyncio

from eggai import Channel
from agents.react_agent import react_agent

agents_channel = Channel("agents")


async def main():
    await react_agent.run()
    await agents_channel.publish({
        "type": "question",
        "payload": "Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building."
    })
    # it should be 3818

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await react_agent.stop()
        await Channel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
