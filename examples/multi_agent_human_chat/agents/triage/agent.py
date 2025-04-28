import time

from eggai import Channel, Agent
from eggai.transport import eggai_set_default_transport, KafkaTransport

from libraries.tracing import TracedMessage, traced_handler, format_span_as_traceparent
from libraries.logger import get_console_logger
from opentelemetry import trace
from .config import settings
from .dspy_modules.classifier_v2 import classifier_v2
from .dspy_modules.small_talk import chatty
from .models import TargetAgent, AGENT_REGISTRY

eggai_set_default_transport(lambda: KafkaTransport(bootstrap_servers=settings.kafka_bootstrap_servers))

triage_agent = Agent(name="TriageAgent")
human_channel = Channel("human")
agents_channel = Channel("agents")

tracer = trace.get_tracer("triage_agent")
logger = get_console_logger("triage_agent.handler")

@triage_agent.subscribe(
    channel=human_channel, filter_by_message=lambda msg: msg.get("type") == "user_message"
)
@traced_handler("handle_user_message")
async def handle_user_message(msg: TracedMessage):
    try:
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
        response = classifier_v2(chat_history=conversation_string)
        processing_time = time.time() - initial_time
        logger.info(f"Classification completed in {processing_time:.2f} seconds")
        
        target_agent = response.target_agent
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        # Get the current span for propagation - this ensures trace continuity
        current_span = trace.get_current_span()
        traceparent, tracestate = format_span_as_traceparent(current_span)

        if target_agent != TargetAgent.ChattyAgent:
            logger.info(f"Routing message to {target_agent}")
            
            # Create a child span for the publish operation
            with tracer.start_as_current_span("publish_to_agent") as publish_span:
                # Get updated trace context from current span
                child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
                await agents_channel.publish(
                    TracedMessage(
                        type=AGENT_REGISTRY[target_agent]["message_type"],
                        source="TriageAgent",
                        data={
                            "chat_messages": triage_to_agent_messages,
                            "message_id": msg.id,
                            "connection_id": connection_id,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
        else:
            message_to_send = chatty(
                chat_history=conversation_string,
            ).response
            
            # Create a child span for the publish operation
            with tracer.start_as_current_span("publish_to_human") as publish_span:
                # Get updated trace context from current span
                child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
                await human_channel.publish(
                    TracedMessage(
                        type="agent_message",
                        source="TriageAgent",
                        data={
                            "message": message_to_send,
                            "message_id": msg.id,
                            "agent": "TriageAgent",
                            "connection_id": connection_id,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
            logger.debug(f"Response sent to user: {message_to_send[:50]}...")
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

@triage_agent.subscribe(channel=human_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)