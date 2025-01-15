import asyncio

from eggai import Channel
from agents.answers_agent import answers_agent

agents_channel = Channel("agents")


async def main():
    await answers_agent.run()

    # Non toxic question
    await agents_channel.publish({
        "type": "question",
        "payload": "What is the year of birth of David Gregory of Kinnairdy castle?"
    })

    # Toxic question
    await agents_channel.publish({
        "type": "question",
        "payload": "Are you stupid??"
    })

    # PII question
    await agents_channel.publish({
        "type": "question",
        "payload": "My email is stefano@gmail.com, is that correct?"
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await answers_agent.stop()
        await Channel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
