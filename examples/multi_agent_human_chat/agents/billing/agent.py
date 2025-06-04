import asyncio
from typing import List

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Agent, Channel

from agents.billing.config import settings
from agents.billing.types import ChatMessage, ModelConfig
from libraries.channels import channels, clear_channels
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)
from libraries.tracing.otel import safe_set_attribute

from .dspy_modules.billing import billing_optimized_dspy

billing_agent = Agent(name="BillingAgent")
logger = get_console_logger("billing_agent.handler")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
tracer = create_tracer("billing_agent")


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


async def process_billing_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float = None,
) -> None:
    """Generate a response to a billing request with streaming output."""
    # Create model config with timeout value
    config = ModelConfig(name="billing_react", timeout_seconds=timeout_seconds or 30.0)
    with tracer.start_as_current_span("process_billing_request") as span:
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "timeout_seconds", config.timeout_seconds)

        if not conversation_string or len(conversation_string.strip()) < 5:
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        # Start the stream
        await human_stream_channel.publish(
            TracedMessage(
                type="agent_message_stream_start",
                source="BillingAgent",
                data={
                    "message_id": message_id,
                    "connection_id": connection_id,
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )
        logger.info(f"Stream started for message {message_id}")

        # Call the model with streaming
        logger.info("Calling billing model with streaming")
        chunks = billing_optimized_dspy(chat_history=conversation_string, config=config)
        chunk_count = 0

        # Process the streaming chunks
        try:
            async for chunk in chunks:
                if isinstance(chunk, StreamResponse):
                    chunk_count += 1
                    await human_stream_channel.publish(
                        TracedMessage(
                            type="agent_message_stream_chunk",
                            source="BillingAgent",
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
                    # Get the complete response
                    response = chunk.final_response
                    if response:
                        response = response.replace(" [[ ## completed ## ]]", "")

                    logger.info(
                        f"Sending stream end with response: {response[:100] if response else 'EMPTY'}"
                    )
                    await human_stream_channel.publish(
                        TracedMessage(
                            type="agent_message_stream_end",
                            source="BillingAgent",
                            data={
                                "message_id": message_id,
                                "message": response,
                                "agent": "BillingAgent",
                                "connection_id": connection_id,
                            },
                            traceparent=child_traceparent,
                            tracestate=child_tracestate,
                        )
                    )
                    logger.info(f"Stream ended for message {message_id}")
        except Exception as e:
            logger.error(f"Error in streaming response: {e}", exc_info=True)
            # Send an error message to end the stream
            await human_stream_channel.publish(
                TracedMessage(
                    type="agent_message_stream_end",
                    source="BillingAgent",
                    data={
                        "message_id": message_id,
                        "message": "I'm sorry, I encountered an error while processing your request.",
                        "agent": "BillingAgent",
                        "connection_id": connection_id,
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )


@billing_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == "billing_request",
    auto_offset_reset="latest",
    group_id="billing_agent_group",
)
@traced_handler("handle_billing_request")
async def handle_billing_request(msg: TracedMessage) -> None:
    """Handle incoming billing request messages from the agents channel."""
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="BillingAgent",
                    data={
                        "message": "I apologize, but I didn't receive any message content to process.",
                        "connection_id": connection_id,
                        "agent": "BillingAgent",
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing billing request for connection {connection_id}")

        await process_billing_request(
            conversation_string, connection_id, str(msg.id), timeout_seconds=30.0
        )

    except Exception as e:
        logger.error(f"Error in BillingAgent: {e}", exc_info=True)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="BillingAgent",
                data={
                    "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",
                    "connection_id": locals().get("connection_id", "unknown"),
                    "agent": "BillingAgent",
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


@billing_agent.subscribe(channel=agents_channel)
@traced_handler("handle_others")
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-billing messages received on the agent channel."""
    logger.debug("Received non-billing message: %s", msg)


if __name__ == "__main__":

    async def run():
        from libraries.dspy_set_language_model import dspy_set_language_model

        dspy_set_language_model(settings)

        await clear_channels()

        test_conversation = (
            "User: How much is my premium?\n"
            "BillingAgent: Could you please provide your policy number?\n"
            "User: It's B67890.\n"
        )

        logger.info("Running test query for billing agent")
        chunks = billing_optimized_dspy(chat_history=test_conversation)
        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                logger.info(f"Chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                logger.info(f"Final response: {chunk.final_response}")

    asyncio.run(run())
