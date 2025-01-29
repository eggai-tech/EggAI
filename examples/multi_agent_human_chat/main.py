import asyncio

from dotenv import load_dotenv
from eggai import eggai_stop
from eggai.transport import eggai_set_default_transport, KafkaTransport

from escalation_agent import escalation_agent
from policies_agent import policy_agent
from server import server
from triage_agent import triage_agent


async def main():
    load_dotenv()
    # UNCOMMENT THIS IF YOU WANT TO RUN IT WITH KAFKA
    # eggai_set_default_transport(lambda: KafkaTransport())

    await triage_agent.start()
    await policy_agent.start()
    await escalation_agent.start()

    server_task = asyncio.create_task(server.serve())

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    await eggai_stop()
    server_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
