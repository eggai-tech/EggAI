import asyncio
from typing import Dict, Any
from eggai import Channel, eggai_cleanup
from eggai.schemas import Message
from agents.react_agent import react_agent
from eggai.transport import KafkaTransport, eggai_set_default_transport

eggai_set_default_transport(lambda: KafkaTransport())


def handle_answer(event: Dict[str, Any]) -> None:
    """Process and display agent response in a structured format"""
    data = event.get("data", {})
    print("\n==== Agent Response ====")
    print(f"Answer: {data.get('answer', 'N/A')}")
    print(f"Numeric: {data.get('numeric_answer', 'N/A')}")
    print(f"Reasoning: {data.get('reasoning', 'N/A')}")
    print("=======================\n")


def handle_question(event: Dict[str, Any]) -> None:
    """Process and display the question in a structured format"""
    data = event.data
    print("\n==== User Question ====")
    print(f"Question: {data.get('message', 'N/A')}")
    print("=======================\n")


async def main():
    agents_channel = Channel("agents")

    await react_agent.start()
    await agents_channel.subscribe(
        filter_by_message=lambda msg: msg["type"] == "answer", callback=handle_answer
    )
    message = Message(
        type="question",
        source="main",
        data={"message": "what's the result of 12345 multiplied by 54321?"},
    )

    handle_question(message)

    await agents_channel.publish(message)

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    await eggai_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
