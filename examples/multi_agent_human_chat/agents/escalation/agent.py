import asyncio
from typing import List

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Agent, Channel
from opentelemetry import trace

from libraries.channels import channels, clear_channels
from libraries.logger import get_console_logger
from libraries.subscribe import subscribe_to_agent_requests
from libraries.tracing import TracedMessage, format_span_as_traceparent, traced_handler
from libraries.tracing.otel import safe_set_attribute

from .config import (
    AGENT_NAME,
    GROUP_ID,
    MSG_TYPE_STREAM_CHUNK,
    MSG_TYPE_STREAM_END,
    MSG_TYPE_STREAM_START,
    dspy_model_config,
    settings,
)

logger = get_console_logger(AGENT_NAME)
from .dspy_modules.escalation import process_escalation
from .types import ChatMessage

ticketing_agent = Agent(name=AGENT_NAME)
agents_channel = Channel(channels.agents)
human_stream_channel = Channel(channels.human_stream)
tracer = trace.get_tracer(AGENT_NAME)



def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    with tracer.start_as_current_span("get_conversation_string") as span:
        safe_set_attribute(
            span, "chat_messages_count", len(chat_messages) if chat_messages else 0
        )

        if not chat_messages:
            safe_set_attribute(span, "empty_messages", True)
            return ""

        conversation_parts = []
        for chat in chat_messages:
            if "content" not in chat:
                safe_set_attribute(span, "invalid_message", True)
                logger.warning("Message missing content field")
                continue

            role = chat.get("role", "User")
            conversation_parts.append(f"{role}: {chat['content']}")

        conversation = "\n".join(conversation_parts) + "\n"
        safe_set_attribute(span, "conversation_length", len(conversation))
        return conversation


async def process_escalation_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float = None,
) -> None:
    config = dspy_model_config
    if timeout_seconds:
        config = dspy_model_config.model_copy(update={"timeout_seconds": timeout_seconds})

    with tracer.start_as_current_span("process_escalation_request") as span:
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "timeout_seconds", config.timeout_seconds)

        if not conversation_string or len(conversation_string.strip()) < 5:
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        await human_stream_channel.publish(
            TracedMessage(
                type=MSG_TYPE_STREAM_START,
                source=AGENT_NAME,
                data={
                    "message_id": message_id,
                    "connection_id": connection_id,
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )
        logger.info(f"Stream started for message {message_id}")

        logger.info("Calling escalation model with streaming")
        chunk_count = 0

        try:
            async for chunk in process_escalation(
                chat_history=conversation_string, config=config
            ):
                if isinstance(chunk, StreamResponse):
                    chunk_count += 1
                    await human_stream_channel.publish(
                        TracedMessage(
                            type=MSG_TYPE_STREAM_CHUNK,
                            source=AGENT_NAME,
                            data={
                                "message_chunk": chunk.chunk,
                                "message_id": message_id,
                                "chunk_index": chunk_count,
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        )
                    )
                elif isinstance(chunk, Prediction):
                    response = chunk.final_response
                    if response:
                        response = response.replace(" [[ ## completed ## ]]", "")

                    logger.info(
                        f"Sending stream end with response: {response[:100] if response else 'EMPTY'}"
                    )
                    await human_stream_channel.publish(
                        TracedMessage(
                            type=MSG_TYPE_STREAM_END,
                            source=AGENT_NAME,
                            data={
                                "message_id": message_id,
                                "message": response,
                                "agent": AGENT_NAME,
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        )
                    )
                    logger.info(f"Stream ended for message {message_id}")
        except Exception as e:
            logger.error(f"Error in streaming response: {e}", exc_info=True)
            await human_stream_channel.publish(
                TracedMessage(
                    type=MSG_TYPE_STREAM_END,
                    source=AGENT_NAME,
                    data={
                        "message_id": message_id,
                        "message": "I'm sorry, I encountered an error while processing your request.",
                        "agent": AGENT_NAME,
                        "connection_id": connection_id,
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )


@subscribe_to_agent_requests(
    agent=ticketing_agent,
    channel=agents_channel,
    request_type="escalation_request",
    group_id=GROUP_ID,
)
@traced_handler("handle_ticketing_request")
async def handle_ticketing_request(msg: TracedMessage) -> None:
    """Handle incoming ticketing request messages with intelligent streaming."""
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            await process_escalation_request(
                "User: [No message content received]",
                connection_id,
                str(msg.id),
                timeout_seconds=30.0,
            )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing ticketing request for connection {connection_id}")

        await process_escalation_request(
            conversation_string, connection_id, str(msg.id), timeout_seconds=60.0
        )

    except Exception as e:
        logger.error(f"Error in TicketingAgent: {e}", exc_info=True)
        try:
            connection_id = locals().get("connection_id", "unknown")
            message_id = str(msg.id) if msg else "unknown"
            await process_escalation_request(
                f"System: Error occurred - {str(e)}",
                connection_id,
                message_id,
                timeout_seconds=60.0,
            )
        except Exception:
            logger.error("Failed to send error response", exc_info=True)


@ticketing_agent.subscribe(channel=agents_channel)
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-ticketing messages received on the agent channel."""
    logger.debug("Received non-ticketing message: %s", msg)


if __name__ == "__main__":

    async def run():
        from libraries.dspy_set_language_model import dspy_set_language_model

        dspy_set_language_model(settings)
        await clear_channels()

        test_conversation = (
            "User: I need to escalate an issue with my policy A12345.\n"
            "TicketingAgent: I can help you with that. Let me check if there are any existing tickets for policy A12345.\n"
            "User: My claim was denied incorrectly and I need this reviewed by technical support. My email is john@example.com.\n"
        )

        logger.info("Running simplified escalation agent test")
        await process_escalation_request(
            test_conversation,
            "test-connection-123",
            "test-message-456",
            timeout_seconds=30.0,
        )

    asyncio.run(run())
