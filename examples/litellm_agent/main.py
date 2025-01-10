import asyncio

from eggai import Channel
from escalate_agent import escalation_agent
from support_agent import support_agent

agents_channel = Channel("agents")
humans_channel = Channel("humans")


async def main():
    await support_agent.run()
    await escalation_agent.run()

    # Simulate a customer inquiry that SupportAgent can handle
    await humans_channel.publish({
        "type": "customer_inquiry",
        "payload": "What is your return policy?"
    })

    # # Simulate a customer inquiry that requires escalation
    await humans_channel.publish({
        "type": "customer_inquiry",
        "payload": "I have a billing issue that isn't resolved yet."
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await support_agent.stop()
        await escalation_agent.stop()
        await Channel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
