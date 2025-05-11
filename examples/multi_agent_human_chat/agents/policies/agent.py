"""Policies agent for handling policy information requests."""
import asyncio
import time
from typing import List

from eggai import Agent, Channel

from agents.policies.config import settings
from agents.policies.dspy_modules.policies import policies_optimized_dspy
from agents.policies.types import ChatMessage, ModelConfig
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)

policies_agent = Agent(name="PoliciesAgent")
logger = get_console_logger("policies_agent.handler")
agents_channel = Channel("agents")
human_channel = Channel("human")
tracer = create_tracer("policies_agent")


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
                logger.warning("Message missing content field")
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
        
        # Validate message format and handle error cases explicitly
        if not message:
            logger.warning("Empty message received")
            message = "I apologize, but I couldn't generate a response. Please try asking your question again."
        elif message == "NoneType" or not isinstance(message, str):
            logger.warning(f"Invalid message format: {type(message)}")
            message = "I'm sorry, there was a technical issue processing your request. Please try again."
            
        publish_span.set_attribute("message_length", len(message))
        publish_span.set_attribute("connection_id", connection_id)
        
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="PoliciesAgent",
                data={
                    "message": message,
                    "connection_id": connection_id,
                    "agent": "PoliciesAgent",
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )
        logger.debug("Response sent successfully")


async def process_policy_request(
    conversation_string: str, 
    connection_id: str,
    timeout_seconds: float = None
) -> str:
    """Generate a response to a policy request with timeout protection."""
    # Create model config with timeout value
    config = ModelConfig(timeout_seconds=timeout_seconds or 30.0)
    
    with tracer.start_as_current_span("process_policy_request") as span:
        span.set_attribute("connection_id", connection_id)
        span.set_attribute("conversation_length", len(conversation_string))
        span.set_attribute("timeout_seconds", config.timeout_seconds)
        
        start_time = time.perf_counter()
        
        # Validate input
        if not conversation_string or len(conversation_string.strip()) < 5:
            span.set_attribute("error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")
            
        # Call the model
        logger.info("Calling policies model")
        response_data = policies_optimized_dspy(chat_history=conversation_string, config=config)
        
        # Record metrics
        processing_time = time.perf_counter() - start_time
        span.set_attribute("processing_time_ms", processing_time * 1000)
        
        # Log response metadata
        if response_data.policy_number:
            logger.info(f"Policy number identified: {response_data.policy_number}")
            span.set_attribute("policy_number", response_data.policy_number)
            
        if response_data.policy_category:
            logger.info(f"Policy category identified: {response_data.policy_category}")
            span.set_attribute("policy_category", str(response_data.policy_category))
            
        if response_data.documentation_reference:
            logger.info(f"Documentation reference: {response_data.documentation_reference}")
            span.set_attribute("has_documentation", True)
        
        # Get the final response
        final_response = response_data.final_response
        
        # Validate response quality
        if not final_response or len(final_response.strip()) < 10:
            span.set_attribute("error", "Invalid or too short response")
            span.set_status(1, "Invalid response")
            logger.warning("Model returned invalid or too short response")
            final_response = "I'm sorry, I couldn't find enough information to answer your question properly. Could you provide more details about your policy inquiry?"
        
        span.set_attribute("response_length", len(final_response))
        return final_response


@policies_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg.get("type") == "policy_request"
)
@traced_handler("handle_policy_request")
async def handle_policy_request(msg: TracedMessage) -> None:
    """Handle incoming policy request messages from the agents channel."""
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
        logger.info(f"Processing policy request for connection {connection_id}")
        logger.debug(f"Conversation context: {conversation_string[:100]}..." if conversation_string else "Empty conversation")

        try:
            final_response = await process_policy_request(conversation_string, connection_id)
            
            logger.info("Sending response to user")
            logger.debug(f"Response: {final_response[:100]}...")
            await publish_agent_response(connection_id, final_response)
            
        except ValueError:
            logger.warning("Invalid input for policy request")
            await publish_agent_response(
                connection_id,
                "Please provide more information about your policy inquiry."
            )
            
        except asyncio.TimeoutError:
            logger.error("Timeout processing policy request")
            await publish_agent_response(
                connection_id,
                "I'm taking longer than expected to process your request. Please try again in a moment."
            )
            
    except Exception as e:
        logger.error(f"Error in PoliciesAgent: {e}", exc_info=True)
        await publish_agent_response(
            connection_id if 'connection_id' in locals() else "unknown",
            "I apologize, but I'm having trouble processing your request right now. Please try again."
        )


@policies_agent.subscribe(channel=agents_channel)
@traced_handler("handle_others")
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-policy messages received on the agent channel."""
    logger.debug("Received non-policy message: %s", msg)


if __name__ == "__main__":
    from libraries.dspy_set_language_model import dspy_set_language_model
    
    dspy_set_language_model(settings)
    test_conversation = (
        "User: I need information about my policy.\n"
        "PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?\n"
        "User: My policy number is A12345\n"
    )

    logger.info("Running test query for policies agent")
    response_data = policies_optimized_dspy(chat_history=test_conversation)
    logger.info(f"Test response: {response_data.final_response}")

