"""
Escalation (Ticketing) DSPy modules for the Escalation Agent.

This module contains the DSPy modules and signatures for the escalation agent,
which handles ticket creation and management for customer issues.
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import dspy

from libraries.logger import get_console_logger
from libraries.tracing import TracedChainOfThought, TracedReAct, create_tracer

from ..types import (
    ConfirmationResponse,
    ModelResult,
    SessionData,
    TicketDepartment,
    TicketInfo,
)

logger = get_console_logger("escalation_agent.dspy")

# Create a tracer for the escalation agent
tracer = create_tracer("ticketing_agent")

# In-memory ticket database
ticket_database: List[Dict] = [{
    "id": "TICKET-001",
    "department": "Technical Support",
    "title": "Billing issue",
    "contact_info": "john@example.com",
    "created_at": datetime.now().isoformat()
}]


# DSPy Signature Definitions
class RetrieveTicketInfoSignature(dspy.Signature):
    """DSPy signature for retrieving ticket information from conversation."""
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    department: TicketDepartment = dspy.OutputField(desc="Department of destination of ticket.")
    title: str = dspy.OutputField(desc="Title of the ticket.")
    contact_info: str = dspy.OutputField(desc="Contact information of the user.")
    info_complete: bool = dspy.OutputField(desc="Whether all required information is present in the chat history or not.")
    message: str = dspy.OutputField(desc="Message to the user, asking for missing information or confirmation.")


class ClassifyConfirmationSignature(dspy.Signature):
    """DSPy signature for classifying user confirmation from conversation."""
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    confirmation: ConfirmationResponse = dspy.OutputField(desc="User confirmation retrieved from chat history.")
    message: str = dspy.OutputField(desc="Message to the user, asking for confirmation.")


class CreateTicketSignature(dspy.Signature):
    """DSPy signature for creating a ticket based on session details."""
    ticket_details: Dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation message confirmation, with summary of ticket details.")


# Tool function
@tracer.start_as_current_span("create_ticket")
def create_ticket(dept: TicketDepartment, title: str, contact: str) -> str:
    """Create a ticket in the database and return the ticket details as JSON."""
    logger.info("Creating ticket in database...")
    ticket = TicketInfo(
        id=f"TICKET-{len(ticket_database) + 1:03}",
        department=dept,
        title=title,
        contact_info=contact,
        created_at=datetime.now().isoformat()
    )
    ticket_dict = ticket.model_dump()
    ticket_database.append(ticket_dict)
    return json.dumps(ticket_dict)


def get_dspy_modules() -> Tuple[dspy.Module, dspy.Module, dspy.Module]:
    """Get DSPy modules for the escalation agent."""
    retrieve_ticket_info_module = dspy.asyncify(
        TracedChainOfThought(
            RetrieveTicketInfoSignature,
            name="retrieve_ticket_info",
            tracer=tracer
        )
    )

    classify_confirmation = dspy.asyncify(
        TracedChainOfThought(
            ClassifyConfirmationSignature,
            name="classify_confirmation",
            tracer=tracer
        )
    )

    create_ticket_module = dspy.asyncify(
        TracedReAct(
            CreateTicketSignature,
            tools=[create_ticket],
            name="create_ticket",
            tracer=tracer,
            max_iters=5
        )
    )

    return retrieve_ticket_info_module, classify_confirmation, create_ticket_module


async def process_ticket_info(
    chat_history: str,
    session_data: SessionData
) -> Tuple[ModelResult, SessionData]:
    """Process ticket information and update session data."""
    start_time = time.perf_counter()
    
    try:
        retrieve_ticket_info_module, _, _ = get_dspy_modules()
        response = await retrieve_ticket_info_module(chat_history=chat_history)
        
        # Update session with collected information
        updated_session = SessionData(**session_data.model_dump())
        for field in ["title", "contact_info", "department"]:
            if hasattr(response, field) and getattr(response, field):
                value = getattr(response, field)
                setattr(updated_session, field, value)
                logger.info(f"Updated {field} in session: {value}")
        
        # Update step if all info is complete
        if response.info_complete:
            logger.info("Information complete. Moving to confirmation step")
            updated_session.step = "ask_confirmation"
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        result = ModelResult(
            message=response.message,
            processing_time_ms=processing_time,
            success=True
        )
        
        return result, updated_session
        
    except Exception as e:
        logger.error(f"Error processing ticket info: {str(e)}", exc_info=True)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ModelResult(
            message="I apologize, but I encountered an error while processing your request. "
                   "Let's try again. Could you please provide your issue details?",
            processing_time_ms=processing_time,
            success=False,
            error=str(e)
        ), session_data


async def process_confirmation(
    chat_history: str,
    session_data: SessionData
) -> Tuple[ModelResult, SessionData, Optional[bool]]:
    """Process user confirmation and update session data."""
    start_time = time.perf_counter()
    
    try:
        _, classify_confirmation_module, _ = get_dspy_modules()
        response = await classify_confirmation_module(chat_history=chat_history)
        
        updated_session = SessionData(**session_data.model_dump())
        confirmed = None
        
        if response.confirmation == "yes":
            logger.info("User confirmed. Moving to ticket creation step")
            updated_session.step = "create_ticket"
            confirmed = True
        else:
            logger.info("User declined. Returning to data collection step")
            updated_session.step = "ask_additional_data"
            confirmed = False
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        result = ModelResult(
            message=response.message,
            processing_time_ms=processing_time,
            success=True
        )
        
        return result, updated_session, confirmed
        
    except Exception as e:
        logger.error(f"Error processing confirmation: {str(e)}", exc_info=True)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ModelResult(
            message="I apologize, but I encountered an error while processing your confirmation. "
                   "Could you please confirm if you'd like to create a ticket with the information provided?",
            processing_time_ms=processing_time,
            success=False,
            error=str(e)
        ), session_data, None


async def create_ticket_from_session(
    session_data: SessionData
) -> ModelResult:
    """Create a ticket using the information in the session data."""
    start_time = time.perf_counter()
    
    try:
        _, _, create_ticket_module = get_dspy_modules()
        response = await create_ticket_module(ticket_details=session_data.model_dump())
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ModelResult(
            message=response.ticket_message,
            processing_time_ms=processing_time,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error creating ticket: {str(e)}", exc_info=True)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ModelResult(
            message="I apologize, but I encountered an error while creating your ticket. "
                   "Please try again later or contact our support team directly.",
            processing_time_ms=processing_time,
            success=False,
            error=str(e)
        )