import json
from typing import Any, Literal
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

# Agent & Channels

# Set up Kafka transport
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

ticketing_agent = Agent(name="TicketingAgent")
agents_channel = Channel("agents")
human_channel = Channel("human")
pending_tickets = {}
tracer = trace.get_tracer("ticketing_agent")

ticket_database = [{
    "id": "TICKET-001",
    "department": "Technical Support",
    "title": "Billing issue",
    "contact_info": "john@example.com"
}]

@tracer.start_as_current_span("create_ticket")
def create_ticket(dept, title, contact):
    """
    Create a ticket with only the department, title, and contact_info fields.
    """
    logger.info("[TOOL] Creating ticket...")
    ticket = {
        "id": f"TICKET-{len(ticket_database) + 1:03}",
        "department": dept,
        "title": title,
        "contact_info": contact
    }
    ticket_database.append(ticket)
    return json.dumps(ticket)

class RetrieveTicketInfoSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    department: Literal["Technical Support", "Billing", "Sales"] = dspy.OutputField(desc="Department of destination of ticket.")
    title: str = dspy.OutputField(desc="Title of the ticket.")
    contact_info: str = dspy.OutputField(desc="Contact information of the user.")
    info_complete: bool = dspy.OutputField(desc="Whether all required information is present in the chat history or not.")
    message: str = dspy.OutputField(desc="Message to the user, asking for missing information or confirmation.")
    

retrieve_ticket_info_module = dspy.asyncify(
    TracedChainOfThought(
        RetrieveTicketInfoSignature, 
        name="retrieve_ticket_info",
        tracer=tracer
    )
)

class ClassifyConfirmationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    confirmation: Literal["yes", "no"] = dspy.OutputField(desc="User confirmation retrieved from chat history.")
    message: str = dspy.OutputField(desc="Message to the user, asking for confirmation.")

classify_confirmation = dspy.asyncify(
    TracedChainOfThought(
        ClassifyConfirmationSignature, 
        name="classify_confirmation",
        tracer=tracer
    )
)

class CreateTicketSignature(dspy.Signature):
    ticket_details: dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation message confirmation, with summary of ticket details.")

# Now only using the create_ticket tool (retrieve_ticket removed)
create_ticket_module = dspy.asyncify(
    TracedReAct(
        CreateTicketSignature, 
        tools=[create_ticket], 
        name="create_ticket",
        tracer=tracer,
        max_iters=5
    )
)

@tracer.start_as_current_span("update_session_data")
def update_session_data(session: str, data: dict):
    if session not in pending_tickets:
        pending_tickets[session] = {}
    pending_tickets[session].update(data)

@tracer.start_as_current_span("agentic_workflow")
async def agentic_workflow(session: str, chat_history: str, meta: Any) -> str:
    step = pending_tickets[session].get("step", "ask_additional_data")

    if step == "ask_additional_data":
        logger.info("[Ticketing Agent] STEP 1: Asking for additional data...")
        response = await retrieve_ticket_info_module(chat_history=chat_history)
        if response.title:
            update_session_data(session, {"title": response.title})
            logger.info(f"[Ticketing Agent] Updating title session: {response.title}")
        if response.contact_info:
            update_session_data(session, {"contact_info": response.contact_info})
            logger.info(f"[Ticketing Agent] Updating contact_info session: {response.contact_info}")
        if response.department:
            update_session_data(session, {"department": response.department})
            logger.info(f"[Ticketing Agent] Updating department session: {response.department}")
        if response.info_complete:
            logger.info("[Ticketing Agent] All information is complete. New step: ask_confirmation")
            update_session_data(session, {"step": "ask_confirmation"})
            
            conf_message = (await classify_confirmation(chat_history=chat_history)).message
            
            logger.info(f"[Ticketing Agent] Sending confirmation message request: {conf_message}")
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="TicketingAgent",
                    data={
                        "message": conf_message,
                        "connection_id": meta.get("connection_id"),
                        "message_id": meta.get("message_id"),
                        "agent": "TicketingAgent",
                        "session": session
                    }
                )
            )
        else:
            logger.info(f"[Ticketing Agent] Information is incomplete. Asking additional details... {response.message}")
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="TicketingAgent",
                    data={
                        "message": response.message,
                        "connection_id": meta.get("connection_id"),
                        "agent": "TicketingAgent",
                        "session": session
                    }
                )
            )
    elif step == "ask_confirmation":
        logger.info("[Ticketing Agent] Processing STEP: Classifying confirmation...")
        response = (await classify_confirmation(chat_history=chat_history))
        if response.confirmation == "yes":
            logger.info("[Ticketing Agent] Confirmation is YES. New step: create_ticket")
            update_session_data(session, {"step": "create_ticket"})
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="TicketingAgent",
                    data={
                        "message": "Creating ticket...",
                        "message_id": meta.get("message_id"),
                        "connection_id": meta.get("connection_id"),
                        "agent": "TicketingAgent",
                        "session": session
                    }
                )
            )
            await agentic_workflow(session, chat_history, meta)
        else:
            logger.info("[Ticketing Agent] Confirmation is NO. New step: ask_additional_data")
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="TicketingAgent",
                    data={
                        "message": response.message,
                        "message_id": meta.get("message_id"),
                        "connection_id": meta.get("connection_id"),
                        "agent": "TicketingAgent",
                        "session": session
                    }
                )
            )
    elif step == "create_ticket":
        logger.info("[Ticketing Agent] Processing STEP: Creating ticket...")
        response = (await create_ticket_module(ticket_details=pending_tickets[session])).ticket_message
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="TicketingAgent",
                data={
                    "message": response,
                    "message_id": meta.get("message_id"),
                    "connection_id": meta.get("connection_id"),
                    "agent": "TicketingAgent",
                    "session": session
                }
            )
        )
        logger.info("[Ticketing Agent] Ticket created. Removing session data...")
        pending_tickets.pop(session, None)
    else:
        raise ValueError("Invalid step value.")

@ticketing_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "ticketing_request"
)
@traced_handler("handle_ticketing_request")
async def handle_ticketing_request(msg_dict):
    logger.info("[Ticketing Agent] Handling ticketing request...")
    msg = TracedMessage(**msg_dict)
    session = msg.data.get("session", f"session_{uuid4()}")
    chat_messages = msg.data.get("chat_messages")
    conversation_string = ""
    for chat in chat_messages:
        role = chat.get("role", "User")
        conversation_string += f"{role}: {chat['content']}\n"
    
    if session not in pending_tickets:
        pending_tickets[session] = { "step": "ask_additional_data" }
    
    await agentic_workflow(session, conversation_string, {
        "session": session,
        "message_id": msg.id,
        "connection_id": msg.data.get("connection_id"),
        "agent": "TicketingAgent"
    })


@ticketing_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)