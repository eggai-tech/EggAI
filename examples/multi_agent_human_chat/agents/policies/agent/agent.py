import asyncio
from typing import List

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Agent, Channel

from agents.policies.agent.reasoning import policies_react_dspy
from agents.policies.config import settings
from agents.policies.types import ChatMessage, ModelConfig
from libraries.channels import channels, clear_channels
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)
from libraries.tracing.init_metrics import init_token_metrics
from libraries.tracing.otel import safe_set_attribute

AGENT_NAME = "PoliciesAgent"
CONSUMER_GROUP_ID = "policies_agent_group"
MESSAGE_TYPE_POLICY_REQUEST = "policy_request"
MESSAGE_TYPE_AGENT_MESSAGE = "agent_message"
MESSAGE_TYPE_STREAM_CHUNK = "agent_message_stream_chunk"
MESSAGE_TYPE_STREAM_END = "agent_message_stream_end"

policies_agent = Agent(name=AGENT_NAME)
logger = get_console_logger("policies_agent.handler")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
tracer = create_tracer("policies_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Format chat messages into a conversation string."""
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


async def process_policy_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float = None,
) -> None:
    """Generate a response to a policy request with streaming output."""
    config = ModelConfig(timeout_seconds=timeout_seconds or 30.0)
    with tracer.start_as_current_span("process_policy_request") as span:
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
                type="agent_message_stream_start",
                source="PoliciesAgent",
                data={
                    "message_id": message_id,
                    "connection_id": connection_id,
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )
        logger.info(f"Stream started for message {message_id}")

        logger.info("Calling policies model with streaming")
        chunks = policies_react_dspy(chat_history=conversation_string, config=config)
        chunk_count = 0

        try:
            async for chunk in chunks:
                if isinstance(chunk, StreamResponse):
                    chunk_count += 1
                    await human_stream_channel.publish(
                        TracedMessage(
                            type=MESSAGE_TYPE_STREAM_CHUNK,
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
                            type=MESSAGE_TYPE_STREAM_END,
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
                    type="agent_message_stream_end",
                    source="PoliciesAgent",
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


@policies_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == MESSAGE_TYPE_POLICY_REQUEST,
    auto_offset_reset="latest",
    group_id=CONSUMER_GROUP_ID,
)
@traced_handler("handle_policy_request")
async def handle_policy_request(msg: TracedMessage) -> None:
    """Handle incoming policy request messages from the agents channel."""
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            await human_channel.publish(
                TracedMessage(
                    type=MESSAGE_TYPE_AGENT_MESSAGE,
                    source=AGENT_NAME,
                    data={
                        "message": "I apologize, but I didn't receive any message content to process.",
                        "connection_id": connection_id,
                        "agent": AGENT_NAME,
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing policy request for connection {connection_id}")

        await process_policy_request(
            conversation_string, connection_id, str(msg.id), timeout_seconds=30.0
        )

    except Exception as e:
        logger.error(f"Error in PoliciesAgent: {e}", exc_info=True)
        await human_channel.publish(
            TracedMessage(
                type=MESSAGE_TYPE_AGENT_MESSAGE,
                source=AGENT_NAME,
                data={
                    "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                    "connection_id": locals().get("connection_id", "unknown"),
                    "agent": AGENT_NAME,
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


@policies_agent.subscribe(channel=agents_channel)
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-policy messages received on the agent channel."""
    logger.debug("Received non-policy message: %s", msg)


if __name__ == "__main__":

    async def run():
        from libraries.dspy_set_language_model import dspy_set_language_model

        dspy_set_language_model(settings)

        await clear_channels()

        test_conversation = (
            "User: I need information about my policy.\n"
            "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
            "User: My policy number is A12345\n"
        )

        logger.info("Running test query for policies agent")
        chunks = policies_react_dspy(chat_history=test_conversation)
        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                logger.info(f"Chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                logger.info(f"Final response: {chunk.final_response}")

    asyncio.run(run())
