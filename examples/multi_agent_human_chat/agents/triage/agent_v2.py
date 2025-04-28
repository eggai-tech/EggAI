from eggai import Channel, Agent

from src.dspy_modules.classifier_v2 import classifier_v2, lm

human_channel = Channel("human")
agents_channel = Channel("agents")

triage_agent = Agent("TriageAgent")

@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message_v2(msg):
    """
    Handles user messages and routes them to the appropriate target agent.
    """
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", "")

        response = classifier_v2(chat_history=chat_messages)

        return {
            "target_agent": response.target_agent,
            "cost": lm.history[-1]["cost"],
        }
    except Exception as e:
        print("Error in Triage Agent: ", e)


if __name__ == "__main__":
    async def main():
        test_event = {
            "type": "user_message",
            "payload": {
                "chat_messages": "User: Hello, I need help with my insurance claim.",
            },
        }
        await handle_user_message_v2(test_event)
    import asyncio
    asyncio.run(main())