"""
Escalation (Ticketing) DSPy modules for the Escalation Agent.

This module contains the DSPy modules and signatures for the escalation agent,
which handles ticket creation and management for customer issues.
"""
import json
import time
from datetime import datetime
from pathlib import Path
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

# Add TicketingSignature for SIMBA optimization
class TicketingSignature(dspy.Signature):
    """
    You are the Escalation Agent for an insurance company.

    ROLE:
    - You manage escalations and create support tickets when issues can't be resolved through normal channels
    - Guide users through the escalation process, collecting necessary information
    - Create tickets and provide reference numbers for tracking
    - Maintain a professional, empathetic tone

    WORKFLOW STAGES:
    1. Initial Assessment: Determine if the issue requires escalation
    2. Information Gathering: Collect department, issue details, and contact information
    3. Confirmation: Verify information before ticket creation
    4. Ticket Creation: Generate ticket and provide reference number
    5. Follow-up: Provide expected response time and next steps

    GUIDELINES:
    - Always ask for missing information one piece at a time
    - Verify all required information before creating a ticket
    - Provide clear confirmation when a ticket is created
    - Be empathetic but professional in your responses
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Response to the user.")

# Path to the SIMBA optimized JSON file
optimized_model_path = Path(__file__).resolve().parent / "optimized_escalation_simba.json"

# Flag to indicate if we're using optimized prompts
using_optimized_prompts = False

# Try to load the optimized JSON file
if optimized_model_path.exists():
    try:
        logger.info(f"Loading optimized prompts from {optimized_model_path}")
        with open(optimized_model_path, 'r') as f:
            optimized_data = json.load(f)

            # Check if the JSON has the expected structure
            if 'react' in optimized_data and 'signature' in optimized_data['react']:
                # Extract the optimized instructions
                optimized_instructions = optimized_data['react']['signature'].get('instructions')
                if optimized_instructions:
                    logger.info("Successfully loaded optimized instructions")
                    # Update the instructions in our signature class
                    TicketingSignature.__doc__ = optimized_instructions
                    using_optimized_prompts = True

            if not using_optimized_prompts:
                logger.warning("Optimized JSON file exists but doesn't have expected structure")
    except Exception as e:
        logger.error(f"Error loading optimized JSON: {e}")
else:
    logger.info(f"Optimized model file not found at {optimized_model_path}")

# Log which prompts we're using
logger.info(f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts for escalation agent")

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
    # Create Chain of Thought modules
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

    # Create standard ticket module with tracer
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