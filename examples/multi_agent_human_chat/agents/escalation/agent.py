import json
from typing import Dict, Literal
from uuid import uuid4

import dspy
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport
from opentelemetry import trace

from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedChainOfThought,
    TracedMessage,
    TracedReAct,
    traced_handler,
)

from .config import settings

logger = get_console_logger("escalation_agent")

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

# Channels and Agent setup
ticketing_agent = Agent(name="TicketingAgent")
agents_channel = Channel("agents")
human_channel = Channel("human")
pending_tickets = {}
tracer = trace.get_tracer("ticketing_agent")

# In-memory ticket database
ticket_database = [{
    "id": "TICKET-001",
    "department": "Technical Support",
    "title": "Billing issue",
    "contact_info": "john@example.com"
}]

# DSPy Signature Definitions
class RetrieveTicketInfoSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    department: Literal["Technical Support", "Billing", "Sales"] = dspy.OutputField(desc="Department of destination of ticket.")
    title: str = dspy.OutputField(desc="Title of the ticket.")
    contact_info: str = dspy.OutputField(desc="Contact information of the user.")
    info_complete: bool = dspy.OutputField(desc="Whether all required information is present in the chat history or not.")
    message: str = dspy.OutputField(desc="Message to the user, asking for missing information or confirmation.")

class ClassifyConfirmationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    confirmation: Literal["yes", "no"] = dspy.OutputField(desc="User confirmation retrieved from chat history.")
    message: str = dspy.OutputField(desc="Message to the user, asking for confirmation.")

class CreateTicketSignature(dspy.Signature):
    ticket_details: dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation message confirmation, with summary of ticket details.")

# Tool function
@tracer.start_as_current_span("create_ticket")
def create_ticket(dept, title, contact):
    logger.info("Creating ticket in database...")
    ticket = {
        "id": f"TICKET-{len(ticket_database) + 1:03}",
        "department": dept,
        "title": title,
        "contact_info": contact
    }
    ticket_database.append(ticket)
    return json.dumps(ticket)

# DSPy modules setup
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

# Session management
def get_session_data(session: str) -> Dict:
    if session not in pending_tickets:
        pending_tickets[session] = {"step": "ask_additional_data"}
    return pending_tickets[session]

@tracer.start_as_current_span("update_session_data")
def update_session_data(session: str, data: dict):
    session_data = get_session_data(session)
    session_data.update(data)

def get_conversation_string(chat_messages):
    conversation = ""
    for chat in chat_messages:
        role = chat.get("role", "User")
        conversation += f"{role}: {chat['content']}\n"
    return conversation

async def send_message_to_user(message, meta):
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

async def handle_data_collection(session: str, chat_history: str, meta: Dict) -> None:
    logger.info("Processing step: Data collection")
    response = await retrieve_ticket_info_module(chat_history=chat_history)
    
    # Update session with collected information
    for field in ["title", "contact_info", "department"]:
        if getattr(response, field):
            value = getattr(response, field)
            update_session_data(session, {field: value})
            logger.info(f"Updated {field} in session: {value}")
    
    if response.info_complete:
        logger.info("Information complete. Moving to confirmation step")
        update_session_data(session, {"step": "ask_confirmation"})
        
        conf_message = (await classify_confirmation(chat_history=chat_history)).message
        logger.info(f"Sending confirmation message: {conf_message}")
        await send_message_to_user(conf_message, meta)
    else:
        logger.info(f"Information incomplete. Requesting more details: {response.message}")
        await send_message_to_user(response.message, meta)

async def handle_confirmation(session: str, chat_history: str, meta: Dict) -> None:
    logger.info("Processing step: Confirmation")
    response = await classify_confirmation(chat_history=chat_history)
    
    if response.confirmation == "yes":
        logger.info("User confirmed. Moving to ticket creation step")
        update_session_data(session, {"step": "create_ticket"})
        await send_message_to_user("Creating ticket...", meta)
        await agentic_workflow(session, chat_history, meta)
    else:
        logger.info("User declined. Returning to data collection step")
        update_session_data(session, {"step": "ask_additional_data"})
        await send_message_to_user(response.message, meta)

async def handle_ticket_creation(session: str, chat_history: str, meta: Dict) -> None:
    logger.info("Processing step: Ticket creation")
    session_data = pending_tickets[session]
    response = (await create_ticket_module(ticket_details=session_data)).ticket_message
    
    await send_message_to_user(response, meta)
    logger.info("Ticket created. Cleaning up session data")
    pending_tickets.pop(session, None)

@tracer.start_as_current_span("agentic_workflow")
async def agentic_workflow(session: str, chat_history: str, meta: Dict) -> None:
    session_data = get_session_data(session)
    step = session_data.get("step", "ask_additional_data")

    if step == "ask_additional_data":
        await handle_data_collection(session, chat_history, meta)
    elif step == "ask_confirmation":
        await handle_confirmation(session, chat_history, meta) 
    elif step == "create_ticket":
        await handle_ticket_creation(session, chat_history, meta)
    else:
        raise ValueError(f"Invalid workflow step: {step}")

@ticketing_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "ticketing_request"
)
@traced_handler("handle_ticketing_request")
async def handle_ticketing_request(msg_dict):
    logger.info("Handling ticketing request")
    msg = TracedMessage(**msg_dict)
    
    session = msg.data.get("session", f"session_{uuid4()}")
    chat_messages = msg.data.get("chat_messages", [])
    conversation_string = get_conversation_string(chat_messages)
    
    meta = {
        "session": session,
        "message_id": msg.id,
        "connection_id": msg.data.get("connection_id", ""),
        "agent": "TicketingAgent"
    }
    
    await agentic_workflow(session, conversation_string, meta)

@ticketing_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)