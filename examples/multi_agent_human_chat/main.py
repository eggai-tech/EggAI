import asyncio

from dotenv import load_dotenv

from sdk.eggai import Channel
from server import server
from triage import triage_agent
from policy import policy_agent
from ticketing import ticketing_agent


async def main():
    await triage_agent.run()
    await policy_agent.run()
    await ticketing_agent.run()

    server_task = asyncio.create_task(server.serve())

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await triage_agent.stop()
        await policy_agent.stop()
        await ticketing_agent.stop()
        await Channel.stop()
        server_task.cancel()


if __name__ == "__main__":
    load_dotenv()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
