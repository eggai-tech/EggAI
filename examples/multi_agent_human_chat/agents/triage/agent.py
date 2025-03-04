import time

from eggai import Channel, Agent
from eggai.schemas import Message
from agents.triage.agents_registry import AGENT_REGISTRY
from agents.triage.dspy_modules.v1 import triage_classifier


triage_agent = Agent(name="TriageAgent")
human_channel = Channel("human")
agents_channel = Channel("agents")



@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg.get("type") == "user_message"
)
async def handle_user_message(msg_dict):
    try:
        msg = Message(**msg_dict)
        chat_messages = msg.data.get("chat_messages", [])

        # Combine chat history
        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"
            
        print("TRIAGE => Classifying message...")
        initial_time = time.time()
        response = triage_classifier(chat_history=conversation_string)
        print(f"TRIAGE => Classification time: {time.time() - initial_time}")
        target_agent = response.target_agent
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            print(f"TRIAGE => Routing to {target_agent}")
            await agents_channel.publish(
                Message(
                    type=AGENT_REGISTRY[target_agent]["message_type"],
                    source="TriageAgent",
                    data={
                        "chat_messages": triage_to_agent_messages,
                        "message_id": msg.id,
                        "connection_id": msg.data.get("connection_id"),
                    },
                )
            )
        else:
            print("TRIAGE => Routing to TriageAgent")
            message_to_send = (
                    response.small_talk_message or response.fall_back_message or ""
            )
            await human_channel.publish(
                Message(
                    type="agent_message",
                    source="TriageAgent",
                    data={
                        "message": message_to_send,
                        "message_id": msg.id,
                        "agent": "TriageAgent",
                        "connection_id": msg.data.get("connection_id"),
                    },
                )
            )
    except Exception as e:
        print("Error in TriageAgent: ", e)
