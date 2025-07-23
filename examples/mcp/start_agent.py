import asyncio

import dotenv
from eggai import Agent, eggai_main, Channel
from eggai.transport import eggai_set_default_transport, KafkaTransport

from eggai_adapter.client import EggaiAdapterClient
from schemas import Ticket, TICKET_ADAPTER_NAME

dotenv.load_dotenv()


@eggai_main
async def main():
    cl = EggaiAdapterClient(TICKET_ADAPTER_NAME)
    tools = await cl.retrieve_tools()
    print(f"Discovered {len(tools)} tools for {TICKET_ADAPTER_NAME}:")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    res = await cl.call_tool("list_tickets", {})

    raw_tickets = res.data if res and not res.is_error else []
    tickets = [Ticket.model_validate(r) for r in raw_tickets] if raw_tickets else []
    print(f"Retrieved {len(tickets)} tickets:")
    for ticket in tickets:
        print(f"- ID: {ticket.id}, Description: {ticket.description}, Status: {ticket.status}")

    if res.is_error:
        print(f"Error retrieving tickets: {res.data}")


    agents_channel = Channel("agents")
    agent = Agent("Agent")

    await agent.start()

    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    eggai_set_default_transport(lambda: KafkaTransport())
    asyncio.run(main())
