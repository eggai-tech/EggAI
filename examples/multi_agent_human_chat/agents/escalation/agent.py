"""
Escalation Agent module.

This module implements the escalation agent for EggAI, which handles
ticket creation and management for user issues that require escalation.
"""
import asyncio
import logging
from typing import Dict
from uuid import uuid4

from eggai import Agent, Channel
from opentelemetry import trace

from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, traced_handler

from .config import settings
from .dspy_modules.escalation import (
    create_ticket_from_session,
    process_confirmation,
    process_ticket_info,
)
from .types import ChatMessage, SessionData

# Configure logger
logger = get_console_logger("escalation_agent")
logger.setLevel(logging.INFO)

# Channels and Agent setup
ticketing_agent = Agent(name="TicketingAgent")
agents_channel = Channel("agents")
human_channel = Channel("human")
tracer = trace.get_tracer("ticketing_agent")

# In-memory session storage
pending_tickets: Dict[str, SessionData] = {}


def get_session_data(session: str) -> SessionData:
    """Get session data for a given session ID, creating it if it doesn't exist."""
    if session not in pending_tickets:
        pending_tickets[session] = SessionData()
    return pending_tickets[session]


@tracer.start_as_current_span("update_session_data")
def update_session_data(session: str, session_data: SessionData) -> None:
    """Update session data for a given session ID."""
    pending_tickets[session] = session_data


def get_conversation_string(chat_messages: list[ChatMessage]) -> str:
    """Convert a list of chat messages to a conversation string."""
    conversation = ""
    for chat in chat_messages:
        role = chat.get("role", "User")
        conversation += f"{role}: {chat['content']}\n"
    return conversation


@tracer.start_as_current_span("publish_agent_response")
async def publish_agent_response(message: str, meta: Dict) -> None:
    """Publish a response from the agent to the human channel."""
    with tracer.start_as_current_span("send_message") as span:
        span.set_attribute("message.length", len(message))
        span.set_attribute("connection_id", meta.get("connection_id", "unknown"))

        try:
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="TicketingAgent",
                    data={
                        "message": message,
                        "connection_id": meta.get("connection_id"),
                        "message_id": meta.get("message_id", ""),
                        "agent": "TicketingAgent",
                        "session": meta.get("session", "")
                    }
                )
            )
            span.set_attribute("message.sent", True)
            logger.debug(f"Published message to human channel: {message[:50]}...")
        except Exception as e:
            span.set_attribute("message.sent", False)
            span.set_attribute("error", str(e))
            logger.error(f"Failed to publish message: {str(e)}", exc_info=True)
            raise


@tracer.start_as_current_span("handle_data_collection")
async def handle_data_collection(session: str, chat_history: str, meta: Dict) -> None:
    """Handle the data collection step of the ticket creation workflow."""
    logger.info("Processing step: Data collection")
    
    session_data = get_session_data(session)
    
    try:
        result, updated_session = await asyncio.wait_for(
            process_ticket_info(chat_history, session_data),
            timeout=settings.timeout_seconds
        )
        
        # Update session with collected information
        update_session_data(session, updated_session)
        
        # Send response to user
        await publish_agent_response(result.message, meta)
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout while processing ticket info for session: {session}")
        error_message = (
            "I'm sorry, but it's taking longer than expected to process your request. "
            "Let me try again. Could you please provide details about your issue?"
        )
        await publish_agent_response(error_message, meta)
    except Exception as e:
        logger.error(f"Error handling data collection: {str(e)}", exc_info=True)
        error_message = (
            "I apologize, but I encountered an error while processing your request. "
            "Let's try again. Could you please provide details about your issue?"
        )
        await publish_agent_response(error_message, meta)


@tracer.start_as_current_span("handle_confirmation")
async def handle_confirmation(session: str, chat_history: str, meta: Dict) -> None:
    """Handle the confirmation step of the ticket creation workflow."""
    logger.info("Processing step: Confirmation")
    
    session_data = get_session_data(session)
    
    try:
        result, updated_session, confirmed = await asyncio.wait_for(
            process_confirmation(chat_history, session_data),
            timeout=settings.timeout_seconds
        )
        
        # Update session with confirmation result
        update_session_data(session, updated_session)
        
        # Send confirmation message to user
        await publish_agent_response(result.message, meta)
        
        # If confirmed, move to ticket creation
        if confirmed:
            await handle_ticket_creation(session, chat_history, meta)
            
    except asyncio.TimeoutError:
        logger.warning(f"Timeout while processing confirmation for session: {session}")
        error_message = (
            "I'm sorry, but it's taking longer than expected to process your confirmation. "
            "Could you please confirm if you'd like to create a ticket with the information provided?"
        )
        await publish_agent_response(error_message, meta)
    except Exception as e:
        logger.error(f"Error handling confirmation: {str(e)}", exc_info=True)
        error_message = (
            "I apologize, but I encountered an error processing your confirmation. "
            "Could you please confirm if the information I collected is correct?"
        )
        await publish_agent_response(error_message, meta)


@tracer.start_as_current_span("handle_ticket_creation")
async def handle_ticket_creation(session: str, chat_history: str, meta: Dict) -> None:
    """Handle the ticket creation step of the workflow."""
    logger.info("Processing step: Ticket creation")
    
    session_data = get_session_data(session)
    
    try:
        result = await asyncio.wait_for(
            create_ticket_from_session(session_data),
            timeout=settings.timeout_seconds
        )
        
        # Send ticket creation confirmation to user
        await publish_agent_response(result.message, meta)
        
        # Clean up session data
        logger.info(f"Ticket created for session {session}. Cleaning up session data.")
        pending_tickets.pop(session, None)
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout while creating ticket for session: {session}")
        error_message = (
            "I'm sorry, but it's taking longer than expected to create your ticket. "
            "Please try again in a moment."
        )
        await publish_agent_response(error_message, meta)
    except Exception as e:
        logger.error(f"Error creating ticket: {str(e)}", exc_info=True)
        error_message = (
            "I apologize, but I encountered an error while creating your ticket. "
            "Please try again later or contact our support team directly."
        )
        await publish_agent_response(error_message, meta)


@tracer.start_as_current_span("agentic_workflow")
async def agentic_workflow(session: str, chat_history: str, meta: Dict) -> None:
    """Process a ticket request through the appropriate workflow step."""
    session_data = get_session_data(session)
    step = session_data.step
    
    logger.info(f"Processing ticket for session: {session}, step: {step}")

    try:
        if step == "ask_additional_data":
            await handle_data_collection(session, chat_history, meta)
        elif step == "ask_confirmation":
            await handle_confirmation(session, chat_history, meta) 
        elif step == "create_ticket":
            await handle_ticket_creation(session, chat_history, meta)
        else:
            logger.error(f"Invalid workflow step: {step}")
            error_message = "I apologize, but I encountered an error. Let's start over."
            await publish_agent_response(error_message, meta)
            # Reset session to beginning
            update_session_data(session, SessionData())
    except Exception as e:
        logger.error(f"Error in agentic_workflow: {str(e)}", exc_info=True)
        error_message = "I apologize, but I encountered an error. Let's try again."
        await publish_agent_response(error_message, meta)


@ticketing_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg.get("type") == "ticketing_request"
)
@traced_handler("handle_ticketing_request")
async def handle_ticketing_request(msg: TracedMessage) -> None:
    """Handle incoming ticketing request messages from the agents channel."""
    logger.info(f"Received ticketing request: {msg.id}")
    
    try:
        # Extract message data with appropriate type checking
        session = msg.data.get("session", f"session_{uuid4()}")
        chat_messages = msg.data.get("chat_messages", [])
        connection_id = msg.data.get("connection_id", "unknown")
        
        logger.info(f"Processing for connection_id: {connection_id}, session: {session}")
        
        # Convert chat messages to conversation string
        conversation_string = get_conversation_string(chat_messages)
        
        # Prepare metadata for response messages
        meta = {
            "session": session,
            "message_id": msg.id,
            "connection_id": connection_id,
            "agent": "TicketingAgent"
        }
        
        # Process the request through the workflow
        await agentic_workflow(session, conversation_string, meta)
        
    except Exception as e:
        logger.error(f"Error handling ticketing request: {str(e)}", exc_info=True)
        # Attempt to send error message if we have connection_id
        try:
            if msg.data.get("connection_id"):
                error_message = (
                    "I apologize, but I encountered an unexpected error. "
                    "Please try again or contact our support team."
                )
                await publish_agent_response(
                    error_message,
                    {
                        "connection_id": msg.data.get("connection_id"),
                        "message_id": msg.id,
                        "agent": "TicketingAgent"
                    }
                )
        except Exception:
            logger.error("Failed to send error message", exc_info=True)


@ticketing_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage) -> None:
    """Handle other messages from the agents channel for debugging."""
    logger.debug(f"Received non-ticketing message: {msg.type}")