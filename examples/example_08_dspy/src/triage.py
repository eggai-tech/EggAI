from uuid import uuid4

from eggai import Channel, Agent
from examples.example_08_dspy.src.agent_registry import AGENT_REGISTRY
from examples.example_08_dspy.src.classifier import classifier, optimized_classifier

human_channel = Channel("human")
agents_channel = Channel("agents")


triage_agent = Agent("TriageAgent")


@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])
        meta = msg.get("meta", {})
        meta["message_id"] = msg.get("id")

        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        #response = classifier(chat_history=conversation_string)
        # WE ARE USING THE OPTIMIZED CLASSIFIER
        response = optimized_classifier(chat_history=conversation_string)

        meta["confidence"] = response.confidence
        meta["reasoning"] = response.reasoning

        target_agent = response.target_agent
        reasoning = response.reasoning
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string}\nReasoning: {reasoning}\n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            await agents_channel.publish(
                {
                    "type": AGENT_REGISTRY[target_agent]["message_type"],
                    "payload": {"chat_messages": triage_to_agent_messages},
                    "meta": meta,
                }
            )
        else:
            meta["agent"] = "TriageAgent"
            await human_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": "agent_message",
                    "meta": meta,
                    "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?",
                }
            )
    except Exception as e:
        print("Error in DSPy Triage Agent: ", e)
