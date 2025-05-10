"""Claims agent for handling insurance claims requests."""
import asyncio
import time
from typing import Any, Dict, List

from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport

from agents.claims.dspy_modules.claims import claims_optimized_dspy
from agents.claims.types import ChatMessage
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)

from .config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

claims_agent = Agent(name="ClaimsAgent")
logger = get_console_logger("claims_agent.handler")
agents_channel = Channel("agents")
human_channel = Channel("human")
tracer = create_tracer("claims_agent")


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Format chat messages into a conversation string."""
    with tracer.start_as_current_span("get_conversation_string") as span:
        span.set_attribute("chat_messages_count", len(chat_messages) if chat_messages else 0)
        
        if not chat_messages:
            span.set_attribute("empty_messages", True)
            return ""
        
        conversation_parts = []
        for chat in chat_messages:
            if "content" not in chat:
                span.set_attribute("invalid_message", True)
                continue
                
            role = chat.get("role", "User")
            conversation_parts.append(f"{role}: {chat['content']}")
            
        conversation = "\n".join(conversation_parts) + "\n"
        span.set_attribute("conversation_length", len(conversation))
        return conversation


async def publish_agent_response(connection_id: str, message: str) -> None:
    """Publish agent response to the human channel."""
    with tracer.start_as_current_span("publish_to_human") as publish_span:
        child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
        
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="ClaimsAgent",
                data={
                    "message": message,
                    "connection_id": connection_id,
                    "agent": "ClaimsAgent",
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )


async def process_claims_request(
    conversation_string: str, 
    connection_id: str,
    timeout_seconds: float = 30.0
) -> str:
    """Generate a response to a claims request with timeout protection."""
    with tracer.start_as_current_span("process_claims_request") as span:
        span.set_attribute("connection_id", connection_id)
        span.set_attribute("conversation_length", len(conversation_string))
        span.set_attribute("timeout_seconds", timeout_seconds)
        
        start_time = time.perf_counter()
        
        try:
            if not conversation_string or len(conversation_string.strip()) < 5:
                span.set_attribute("error", "Empty or too short conversation")
                span.set_status(1, "Invalid input")
                raise ValueError("Conversation history is too short to process")
                
            logger.info("Calling claims model")
            result = claims_optimized_dspy(chat_history=conversation_string)
            
            if not result or len(result.strip()) < 10:
                span.set_attribute("error", "Empty or too short response")
                span.set_status(1, "Invalid response")
                return "I apologize, but I couldn't generate a proper response. Please try asking again."
            processing_time = time.perf_counter() - start_time
            span.set_attribute("processing_time_ms", processing_time * 1000)
            span.set_attribute("response_length", len(result))
            
            return result
            
        except asyncio.TimeoutError:
            processing_time = time.perf_counter() - start_time
            span.set_attribute("processing_time_ms", processing_time * 1000)
            span.set_attribute("error", "Timeout")
            span.set_status(1, "Timeout")
            logger.error(f"Timeout processing claims request after {processing_time:.2f}s")
            raise TimeoutError(f"Claims processing timed out after {timeout_seconds} seconds")
            
        except ValueError as ve:
            processing_time = time.perf_counter() - start_time
            span.set_attribute("processing_time_ms", processing_time * 1000)
            span.set_attribute("error", str(ve))
            span.set_status(1, str(ve))
            logger.error(f"Validation error in claims processing: {ve}")
            raise
            
        except Exception as e:
            processing_time = time.perf_counter() - start_time
            span.set_attribute("processing_time_ms", processing_time * 1000)
            span.set_attribute("error", str(e))
            span.set_status(1, str(e))
            logger.error(f"Error in claims processing: {e}", exc_info=True)
            raise


@claims_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "claim_request"
)
@traced_handler("handle_claims_message")
async def handle_claims_message(msg_dict: Dict[str, Any]) -> None:  # Using Dict for backward compatibility with @traced_handler
    """Handle incoming claims message from agents channel."""
    connection_id = "unknown"
    try:
        msg = TracedMessage(**msg_dict)
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            await publish_agent_response(
                connection_id,
                "I apologize, but I didn't receive any message content to process."
            )
            return
            
        conversation_string = get_conversation_string(chat_messages)
        logger.info("Processing claims request")
        logger.debug(f"Conversation context: {conversation_string[:100]}..." if conversation_string else "Empty conversation")

        final_text = await process_claims_request(conversation_string, connection_id)

        logger.info("Sending response to user")
        logger.debug(f"Response: {final_text[:100]}...")
        await publish_agent_response(connection_id, final_text)
        
    except ValueError as ve:
        logger.warning(f"Validation error in claims request: {ve}")
        # Sanitize error message - don't expose internal details
        error_message = "Please provide valid information for your claim request."
        await publish_agent_response(connection_id, error_message)
        
    except TimeoutError:
        logger.error("Timeout processing claims request")
        await publish_agent_response(
            connection_id,
            "I'm taking longer than expected to process your request. Please try again in a moment."
        )
        
    except Exception as e:
        logger.error(f"Error in ClaimsAgent: {e}", exc_info=True)
        await publish_agent_response(
            connection_id,
            "An unexpected error occurred while processing your request. Please try again."
        )


@claims_agent.subscribe(channel=agents_channel)
@traced_handler("handle_others")
async def handle_other_messages(msg_dict: Dict[str, Any]) -> None:  # Using Dict for backward compatibility with @traced_handler
    """Handle non-claim messages received on the agent channel."""
    with tracer.start_as_current_span("handle_other_messages") as span:
        try:
            msg = TracedMessage(**msg_dict)
            # Add tracing attributes for observability
            span.set_attribute("message_type", msg.type if hasattr(msg, "type") else "unknown")
            span.set_attribute("message_source", msg.source if hasattr(msg, "source") else "unknown")
            logger.debug("Received non-claim message: %s", msg)
        except Exception as e:
            span.set_attribute("error", str(e))
            span.set_status(1, str(e))
            logger.error(f"Error handling message: {e}", exc_info=True)


if __name__ == "__main__":
    dspy_set_language_model(settings)
    test_conversation = (
        "User: Hi, I'd like to file a new claim.\n"
        "ClaimsAgent: Certainly! Could you provide your policy number and incident details?\n"
        "User: Policy A12345, my car was hit at a stop sign.\n"
    )

    logger.info("Running test query for claims agent")
    result = claims_optimized_dspy(chat_history=test_conversation)
    logger.info(f"Test response: {result}")