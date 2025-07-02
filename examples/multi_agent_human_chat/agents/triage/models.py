from enum import Enum

from pydantic import BaseModel


class TargetAgent(str, Enum):
    BillingAgent = "BillingAgent"
    PolicyAgent = "PolicyAgent"
    ClaimsAgent = "ClaimsAgent"
    EscalationAgent = "EscalationAgent"
    ChattyAgent = "ChattyAgent"


class ClassifierVersion(str, Enum):
    """Supported classifier versions."""

    v0 = "v0"
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"
    v4 = "v4"
    v5 = "v5"


class ClassifierMetrics(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


AGENT_REGISTRY = {
    TargetAgent.BillingAgent: {
        "description": "Handling invoices, bills, payments, payment methods, receipts, refunds, and all financial transactions",
        "message_type": "billing_request",
    },
    TargetAgent.PolicyAgent: {
        "description": "Explaining policy coverage, terms, conditions, policy changes, renewals, and policy documents. You will always ask the user for their policy number first.",
        "message_type": "policy_request",
    },
    TargetAgent.ClaimsAgent: {
        "description": "Processing new claims, claim status inquiries, incident reports, claim documentation, and claim history. You will always ask the user for their claim number first.",
        "message_type": "claim_request",
    },
    TargetAgent.EscalationAgent: {
        "description": "Handling escalations and requests to speak with managers, or technical issues not solvable from the other agents, e.g. login problems, and system errors. His context is to create a Ticket about the problem. If the user asks about previous ticket, you always ask for ticket number.",
        "message_type": "ticketing_request",
    },
    TargetAgent.ChattyAgent: {
        "description": "The fallback agent, engaging in friendly conversation, responding to greetings and guiding users to ask about their insurance needs. When User asks about an off topic question, you will kindly redirect the user to ask about their insurance needs, specifying that you are not a human and cannot answer those questions."
    },
}


def formatted_agent_registry():
    """
    Formats the AGENT_REGISTRY dictionary into a string representation for display.
    """
    formatted_str = ""
    for agent, details in AGENT_REGISTRY.items():
        formatted_str += f"{agent.value}: {details['description']}\n"
    return formatted_str
