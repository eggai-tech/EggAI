"""Claims agent for handling insurance claims requests."""
import asyncio
import time
from typing import List

from eggai import Agent, Channel

from agents.claims.config import settings
from agents.claims.dspy_modules.claims import claims_optimized_dspy
from agents.claims.types import ChatMessage
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
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
        
        # Validate input
        if not conversation_string or len(conversation_string.strip()) < 5:
            span.set_attribute("error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")
            
        # Call the model
        logger.info("Calling claims model")
        result = claims_optimized_dspy(chat_history=conversation_string)
        
        # Record metrics
        processing_time = time.perf_counter() - start_time
        span.set_attribute("processing_time_ms", processing_time * 1000)
        span.set_attribute("response_length", len(result))
        
        # Validate response
        if not result or len(result.strip()) < 10:
            span.set_attribute("error", "Empty or too short response")
            span.set_status(1, "Invalid response")
            return "I apologize, but I couldn't generate a proper response. Please try asking again."
        
        return result


@claims_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg.get("type") == "claim_request"
)
@traced_handler("handle_claims_message")
async def handle_claims_message(msg: TracedMessage) -> None:
    """Handle incoming claims message from agents channel."""
    try:
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

        try:
            final_text = await process_claims_request(conversation_string, connection_id)
            
            logger.info("Sending response to user")
            logger.debug(f"Response: {final_text[:100]}...")
            await publish_agent_response(connection_id, final_text)
            
        except ValueError:
            logger.warning("Invalid input for claims request")
            await publish_agent_response(
                connection_id,
                "Please provide valid information for your claim request."
            )
            
        except asyncio.TimeoutError:
            logger.error("Timeout processing claims request")
            await publish_agent_response(
                connection_id,
                "I'm taking longer than expected to process your request. Please try again in a moment."
            )
            
    except Exception as e:
        logger.error(f"Error in ClaimsAgent: {e}", exc_info=True)
        await publish_agent_response(
            connection_id if 'connection_id' in locals() else "unknown",
            "An unexpected error occurred while processing your request. Please try again."
        )


if __name__ == "__main__":
    from libraries.dspy_set_language_model import dspy_set_language_model
    
    dspy_set_language_model(settings)
    test_conversation = (
        "User: Hi, I'd like to file a new claim.\n"
        "ClaimsAgent: Certainly! Could you provide your policy number and incident details?\n"
        "User: Policy A12345, my car was hit at a stop sign.\n"
    )

    logger.info("Running test query for claims agent")
    result = claims_optimized_dspy(chat_history=test_conversation)
    logger.info(f"Test response: {result}")