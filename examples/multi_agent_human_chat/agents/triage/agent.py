import time

from eggai import Channel, Agent
from eggai.schemas import Message
from agents.triage.agents_registry import AGENT_REGISTRY
from agents.triage.dspy_modules.v1 import triage_classifier
from libraries.logger import get_console_logger
from opentelemetry import trace

triage_agent = Agent(name="TriageAgent")
human_channel = Channel("human")
agents_channel = Channel("agents")

tracer = trace.get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")

@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg.get("type") == "user_message"
)
@tracer.start_as_current_span("handle_user_message")
async def handle_user_message(msg_dict):
    try:
        msg = Message(**msg_dict)
        chat_messages = msg.data.get("chat_messages", [])
        connection_id = msg.data.get("connection_id", "unknown")
        
        logger.info(f"Received message from connection {connection_id}")
        logger.debug(f"Message content: {msg.id}")

        # Combine chat history
        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"
        
        logger.info("Classifying message...")
        initial_time = time.time()
        response = triage_classifier(chat_history=conversation_string)
        processing_time = time.time() - initial_time
        logger.info(f"Classification completed in {processing_time:.2f} seconds")
        
        target_agent = response.target_agent
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            logger.info(f"Routing message to {target_agent}")
            await agents_channel.publish(
                Message(
                    type=AGENT_REGISTRY[target_agent]["message_type"],
                    source="TriageAgent",
                    data={
                        "chat_messages": triage_to_agent_messages,
                        "message_id": msg.id,
                        "connection_id": connection_id,
                    },
                )
            )
            logger.debug(f"Message sent to {target_agent} via {AGENT_REGISTRY[target_agent]['message_type']} channel")
        else:
            logger.info("Handling message with TriageAgent")
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
                        "connection_id": connection_id,
                    },
                )
            )
            logger.debug(f"Response sent to user: {message_to_send[:50]}...")
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
