from triage_agent_dataset.models import Agents

AGENT_REGISTRY = {
    Agents.BILLING: {
        "description": "Handling invoices, bills, payments, payment methods, receipts, refunds, and all financial transactions."
    },
    Agents.POLICY: {
        "description": (
            "Explaining policy coverage, terms, conditions, policy changes, renewals, and policy documents. "
            "You will always ask the user for their policy number first."
        )
    },
    Agents.CLAIMS: {
        "description": (
            "Processing new claims, claim status inquiries, incident reports, claim documentation, and claim history. "
            "You will always ask the user for their claim number first."
        )
    },
    Agents.ESCALATION: {
        "description": (
            "Handling escalations and requests to speak with managers, or technical issues not solvable from the other agents, "
            "e.g. login problems, and system errors. His context is to create a Ticket about the problem. "
            "If the user asks about previous ticket, you always ask for ticket number."
        )
    },
    Agents.CHATTY: {
        "description": (
            "The fallback agent, engaging in friendly conversation, responding to greetings and guiding users to ask about "
            "their insurance needs. When User asks about an off topic question, you will kindly redirect the user to ask "
            "about their insurance needs, specifying that you are not a human and cannot answer those questions."
        )
    }
}

formatted_registry = "\n".join(
    [f"- {agent.value}: {details['description']}" for agent, details in AGENT_REGISTRY.items()]
)

SYSTEM_PROMPT = f"""
You are a dataset generator for an insurance support chatbot classifier. The Classifier is trained to route the conversation to the correct agent.
This is the Agent Registry: 
{formatted_registry}

The goal is to generate a dataset of conversations that can be used to train the classifier with the related target agent.
The conversation should be realistic, short.
A conversation consists of multiple turns. Each turn is a message from the user or the agent. The first and the latest turn are from the user.

The conversation begins with identifier #conversation#, and is a text block with the following format:
#conversation#
User: <user message>
Agent: <agent message>
User: <user message>

After the conversation is generated you have to provide the target agent for the conversation using the following format: #target_agent# <AgentName>
The AgentName should be one of the following: BillingAgent, PolicyAgent, ClaimsAgent, EscalationAgent, ChattyAgent.

Example:

#conversation#
User: Hello, I have a question about my bill.
BillingAgent: Sure, I can help you with that. What is your question?
User: I was charged twice for the same service.

#target_agent# BillingAgent

Another example:

#conversation#
User: What is the status of my claim?

#target_agent# ClaimsAgent

The conversation should be realistic, short and should not contain any sensitive information.
"""

SPECIAL_CASE_ADDITIONAL_INSTRUCTIONS = {
    "edge_case": (
        "Create a tricky edge case scenario for the #target_agent# that's unusual but still valid.\n"
        "The conversation should involve a rare or uncommon situation that still falls under #target_agent#'s domain."
    ),
    "cross_domain": "Create a conversation that involves multiple agents, but the #target_agent# is the most relevant one to the latest user message.",
    "language_switch": "Create a conversation that switches between two languages. The #target_agent# should be able to handle both languages.",
    "short_query": "Create a very short user message that still requires the #target_agent# to provide a meaningful response.",
    "complex_query": "Create a complex user message that requires the #target_agent# to ask clarifying questions before providing an answer.",
    "small_talk": "Create a conversation that starts with small talk but eventually leads to a relevant question for the #target_agent#.",
    "angry_customer": (
        "Create a conversation where the user is angry or frustrated, and the #target_agent# needs to handle the situation delicately.\n"
        "The customer will even use profanity and insults."
    ),
    "technical_error": "Create a conversation that presents a technical error scenario requiring the #target_agent# to manage system issues."
}
