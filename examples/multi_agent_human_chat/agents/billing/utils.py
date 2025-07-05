import asyncio
from typing import List, Optional

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Channel

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, format_span_as_traceparent
from libraries.tracing.otel import safe_set_attribute

from .dspy_modules.billing import billing_optimized_dspy
from .types import ChatMessage, ModelConfig

# Default human stream channel for the Billing Agent
default_human_stream_channel = Channel(channels.human_stream)

logger = get_console_logger("billing_agent.utils")
tracer = create_tracer("billing_agent")


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Format chat messages into a conversation string."""
    with tracer.start_as_current_span("get_conversation_string") as span:
        safe_set_attribute(
            span,
            "chat_messages_count",
            len(chat_messages) if chat_messages else 0,
        )

        if not chat_messages:
            safe_set_attribute(span, "empty_messages", True)
            return ""

        conversation_parts: List[str] = []
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
    human_stream_channel: Channel = default_human_stream_channel,
    timeout_seconds: Optional[float] = None,
) -> None:
    """Generate a streaming response to a billing request."""
    config = ModelConfig(name="billing_react", timeout_seconds=timeout_seconds or 30.0)
    with tracer.start_as_current_span("process_billing_request") as span:
        tp, ts = format_span_as_traceparent(span)
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "timeout_seconds", config.timeout_seconds)

        if not conversation_string or len(conversation_string.strip()) < 5:
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        # signal stream start
        await human_stream_channel.publish(
            TracedMessage(
                type="agent_message_stream_start",
                source=tracer.name,
                data={"message_id": message_id, "connection_id": connection_id},
                traceparent=tp,
                tracestate=ts,
            )
        )

        count = 0

        try:
            async for chunk in billing_optimized_dspy(chat_history=conversation_string, config=config):
                if isinstance(chunk, StreamResponse):
                    count += 1
                    await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_chunk",
                        source=tracer.name,
                            data={
                                "message_chunk": chunk.chunk,
                                "message_id": message_id,
                                "chunk_index": count,
                                "connection_id": connection_id,
                            },
                            traceparent=tp,
                            tracestate=ts,
                        )
                    )
                elif isinstance(chunk, Prediction):
                    resp = chunk.final_response or ""
                    resp = resp.replace(" [[ ## completed ## ]]", "")
                    await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source=tracer.name,
                            data={
                                "message_id": message_id,
                                "message": resp,
                                "connection_id": connection_id,
                            },
                            traceparent=tp,
                            tracestate=ts,
                        )
                    )
        except asyncio.CancelledError:
            raise
        except ValueError as ve:
            safe_set_attribute(span, "error", str(ve))
            span.set_status(1, str(ve))
            await human_stream_channel.publish(
            TracedMessage(
                    type="agent_message_stream_end",
                    source=tracer.name,
                    data={
                        "message_id": message_id,
                        "message": str(ve),
                        "connection_id": connection_id,
                    },
                    traceparent=tp,
                    tracestate=ts,
                )
            )
            return
        except Exception as e:
            safe_set_attribute(span, "error", str(e))
            span.set_status(1, str(e))
            logger.error(f"Error during billing stream: {e}", exc_info=True)
            await human_stream_channel.publish(
                TracedMessage(
                    type="agent_message_stream_end",
                    source=tracer.name,
                    data={
                        "message_id": message_id,
                        "message": f"Error processing billing request: {e}",
                        "connection_id": connection_id,
                    },
                    traceparent=tp,
                    tracestate=ts,
                )
            )
            return

