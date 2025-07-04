"""
Escalation (Ticketing) DSPy modules for the Escalation Agent.

This module contains the DSPy modules and signatures for the escalation agent,
which handles ticket creation and management for customer issues.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import AsyncIterable, Dict, List, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse

from agents.escalation.types import (
    DspyModelConfig,
    TicketDepartment,
    TicketInfo,
)
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedReAct,
    create_tracer,
    traced_dspy_function,
)

logger = get_console_logger("escalation_agent.dspy")

tracer = create_tracer("ticketing_agent")


class TicketingSignature(dspy.Signature):
    """
    You are the Escalation Agent for an insurance company. You handle ticket creation and management intelligently.

    CORE RESPONSIBILITIES:
    - Check conversation history to extract policy numbers and issue details
    - ALWAYS search for existing tickets first using get_tickets_by_policy
    - Collect missing information naturally through conversation
    - Create tickets when you have: policy_number, department, title, contact_info
    - Provide helpful updates on existing tickets when found

    POLICY NUMBER RULES:
    - MANDATORY for all ticket operations (format: A12345, B67890, etc.)
    - If missing, ask: "I need your policy number to help with this escalation. Could you provide it?"
    - ALWAYS check existing tickets first with get_tickets_by_policy before creating new ones

    INTELLIGENT WORKFLOW:
    1. Extract policy number from conversation history
    2. Check existing tickets with get_tickets_by_policy(policy_number)
    3. If existing tickets found, summarize them and ask if this is related
    4. Collect any missing info: department (Technical Support/Billing/Sales), issue title, contact info
    5. When all info ready, create ticket with create_ticket(policy_number, dept, title, contact)
    6. Confirm ticket creation with details and next steps

    DEPARTMENT MAPPING:
    - Technical issues, login problems, website issues → "Technical Support"
    - Payment issues, billing disputes, premium questions → "Billing"
    - Policy purchases, quotes, coverage questions → "Sales"

    BE CONVERSATIONAL:
    - Don't ask for info already in conversation history
    - Reference existing tickets naturally: "I see you have ticket TICKET-001 for a website issue. Is this related?"
    - Create tickets when you have sufficient information without asking for confirmation
    - Be empathetic and professional
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Response to the user.")


optimized_model_path = (
    Path(__file__).resolve().parent / "optimized_escalation_simba.json"
)

using_optimized_prompts = False

if optimized_model_path.exists():
    try:
        logger.info(f"Loading optimized prompts from {optimized_model_path}")
        with open(optimized_model_path, "r") as f:
            optimized_data = json.load(f)

            if "react" in optimized_data and "signature" in optimized_data["react"]:
                optimized_instructions = optimized_data["react"]["signature"].get(
                    "instructions"
                )
                if optimized_instructions:
                    logger.info("Successfully loaded optimized instructions")
                    TicketingSignature.__doc__ = optimized_instructions
                    using_optimized_prompts = True

            if not using_optimized_prompts:
                logger.warning(
                    "Optimized JSON file exists but doesn't have expected structure"
                )
    except Exception as e:
        logger.error(f"Error loading optimized JSON: {e}")
else:
    logger.info(f"Optimized model file not found at {optimized_model_path}")

logger.info(
    f"Using {'optimized' if using_optimized_prompts else 'standard'} prompts for escalation agent"
)


@tracer.start_as_current_span("get_tickets_by_policy")
def get_tickets_by_policy(policy_number: str) -> str:
    """Retrieve all tickets associated with a policy number from the database.

    Strips leading/trailing whitespace from the provided policy number before lookup."""
    cleaned = policy_number.strip()
    logger.info(f"Searching for tickets with policy number: {cleaned!r}")

    matching_tickets = [
        ticket
        for ticket in ticket_database
        if ticket.get("policy_number") == cleaned
    ]

    if not matching_tickets:
        return json.dumps(
            {
                "found": False,
                "message": f"No tickets found for policy number {cleaned}",
                "tickets": [],
            }
        )

    return json.dumps(
        {
            "found": True,
            "message": f"Found {len(matching_tickets)} ticket(s) for policy number {cleaned}",
            "tickets": matching_tickets,
        }
    )


@tracer.start_as_current_span("create_ticket")
def create_ticket(
    policy_number: str, dept: TicketDepartment, title: str, contact: str
) -> str:
    """Create a ticket in the database and return the ticket details as JSON."""
    logger.info("Creating ticket in database...")
    ticket = TicketInfo(
        id=f"TICKET-{len(ticket_database) + 1:03}",
        policy_number=policy_number,
        department=dept,
        title=title,
        contact_info=contact,
        created_at=datetime.now().isoformat(),
    )
    ticket_dict = ticket.model_dump()
    ticket_database.append(ticket_dict)
    return json.dumps(ticket_dict)


# Create a main escalation model for streaming
escalation_model = TracedReAct(
    TicketingSignature,
    tools=[get_tickets_by_policy, create_ticket],
    name="escalation_react",
    tracer=tracer,
    max_iters=5,
)

ticket_database: List[Dict] = [
    {
        "id": "TICKET-001",
        "policy_number": "A12345",
        "department": "Technical Support",
        "title": "I can't access my account on the website",
        "contact_info": "john@example.com",
        "created_at": datetime.now().isoformat(),
    }
]


@traced_dspy_function(name="escalation_dspy")
async def escalation_optimized_dspy(
    chat_history: str, config: Optional[DspyModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Process an escalation inquiry using the DSPy model with streaming output."""
    config = config or DspyModelConfig()

    streamify_func = dspy.streamify(
        escalation_model,
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="final_response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True,
    )

    async for chunk in streamify_func(chat_history=chat_history):
        yield chunk


if __name__ == "__main__":

    async def run():
        from agents.escalation.config import settings
        from libraries.dspy_set_language_model import dspy_set_language_model
        from libraries.tracing import init_telemetry

        init_telemetry(settings.app_name, endpoint=settings.otel_endpoint)
        dspy_set_language_model(settings)

        # Test the escalation DSPy module
        test_conversation = (
            "User: I need to escalate an issue with my policy A12345.\n"
            "TicketingAgent: I can help you with that. Let me check if there are any existing tickets for policy A12345.\n"
            "User: My claim was denied incorrectly and I need this reviewed by technical support.\n"
        )

        logger.info("Running test query for escalation agent")
        chunks = escalation_optimized_dspy(test_conversation)

        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                print(f"Stream chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                result = chunk
                print(f"Final response: {result.final_response}")

    import asyncio

    asyncio.run(run())
