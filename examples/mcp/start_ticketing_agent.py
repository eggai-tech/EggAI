import asyncio
import os

import dotenv
import dspy
from eggai import Agent, eggai_main, Channel
from eggai.schemas import Message
from eggai.transport import eggai_set_default_transport, KafkaTransport

from eggai_adapter.client import EggaiAdapterClient
from eggai_adapter.dspy import convert_tool_for_dspy
from schemas import TICKET_ADAPTER_NAME


class TicketAssistantSignature(dspy.Signature):
    """You are an helpful assistant that can interact with external tools to manage support tickets."""
    conversation_history: str = dspy.InputField()
    user_message: str = dspy.InputField()
    assistant_response: str = dspy.OutputField()


dotenv.load_dotenv()
dspy.configure(
    lm=dspy.LM(model="openai/gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
)


async def initialize_ticketing_agent():
    agent = Agent("TicketingAgent")

    conversation_history = []

    cl = EggaiAdapterClient(TICKET_ADAPTER_NAME)
    tools = await cl.retrieve_tools()

    react = dspy.ReAct(
        signature=TicketAssistantSignature,
        tools=[convert_tool_for_dspy(cl, tool) for tool in tools],
        max_iters=5
    )


    @agent.subscribe(channel=Channel("human.in"))
    async def handle_user_input(message: Message):
        user_message = message.data.get("user_message")

        conversation_history.append("User: " + user_message)

        response = await react.aforward(
            conversation_history=conversation_history,
            user_message=user_message
        )
        conversation_history.append("Assistant: " + response.assistant_response)

        await Channel("human.out").publish(
            Message(
                type="agent_response",
                source="TicketingAgent",
                data={
                    "assistant_response": response.assistant_response
                }
            )
        )

    return agent


@eggai_main
async def main():
    agent = await initialize_ticketing_agent()
    await agent.start()

    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    eggai_set_default_transport(lambda: KafkaTransport())
    asyncio.run(main())
