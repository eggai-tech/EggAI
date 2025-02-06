from uuid import uuid4
import dspy
from eggai import Channel, Agent
from agents.triage.agents_registry import AGENT_REGISTRY
from agents.triage.dspy_modules.v1 import AgentClassificationSignature

human_channel = Channel("human")
agents_channel = Channel("agents")

triage_classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
triage_agent = Agent(name="TriageAgent")


@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])
        meta = msg.get("meta", {})
        meta["message_id"] = msg.get("id")

        # Combine chat history
        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        # identify the agent to target based on the user chat messages
        response = triage_classifier(chat_history=conversation_string)
        target_agent = response.target_agent
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            await agents_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": AGENT_REGISTRY[target_agent]["message_type"],
                    "payload": {"chat_messages": triage_to_agent_messages},
                    "meta": meta,
                }
            )
        else:
            message_to_send = (
                response.small_talk_message or response.fall_back_message or ""
            )
            meta["agent"] = "TriageAgent"
            await human_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": "agent_message",
                    "meta": meta,
                    "payload": message_to_send,
                }
            )
    except Exception as e:
        print("Error in TriageAgent: ", e)
