import json
import os

import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.models import (
    ClassifierMetrics,
    TargetAgent,
    formatted_agent_registry,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

settings = Settings()
logger = get_console_logger("triage_classifier_v4")

load_dotenv()
lm = dspy_set_language_model(settings)


class AgentClassificationSignature(dspy.Signature):
    def __init__(self, chat_history: str):
        super().__init__(chat_history=chat_history)
        self.metrics: ClassifierMetrics

    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )


# Improved zero-shot prompt with detailed classification rules
ZERO_SHOT_INSTRUCTIONS = (
    """
You are an intelligent classifier in a multi-agent insurance support system. Your task is to analyze the chat history and determine which specialized agent should handle the user's query.

## Available Target Agents:
"""
    + formatted_agent_registry()
    + """

## Classification Rules:
1. If the query is about bills, payments, invoices, paperless billing, payment methods, late payment fees, fee calculations, refunds, or ANY financial matters → BillingAgent
2. If the query is about policy, policy details, coverage, terms, renewals, or documents → PolicyAgent
3. If the query is about filing a claim, processing a claim, claim status, or claim documentation → ClaimsAgent
4. If the query involves issues requiring escalation, speaking with managers, or technical problems → EscalationAgent
5. If the query is a greeting, casual conversation, or non-insurance related → ChattyAgent (fallback)

## Important Disambiguation Rules:
- ALL payment-related topics, including late payment fees, payment failures, and REFUNDS, should go to BillingAgent, NOT PolicyAgent
- ANY question about how fees work or how fees are calculated should go to BillingAgent
- Questions about the claims appeal process should go to ClaimsAgent, NOT PolicyAgent
- Refund requests or refund status inquiries go to BillingAgent, NOT ClaimsAgent
- When a user mentions transaction IDs, this typically relates to billing issues, so route to BillingAgent
- Paperless billing setup, billing preferences, or account changes should go to BillingAgent
- If a conversation is already in progress with an agent, maintain continuity by routing to the same agent

## Decision Process:
1. First, check if the query contains explicit indicators like transaction IDs, refund requests, payment terms, etc.
2. Analyze the entire chat history to understand context and previous agent interactions
3. Identify key terms and topics related to insurance domains
4. Apply the disambiguation rules to resolve common confusion points
5. Match these topics to the most appropriate specialized agent
6. If the query contains no insurance-related content, route to ChattyAgent

Return only the name of the target agent without explanation.
"""
)

classifier_v4_program = dspy.Predict(
    signature=AgentClassificationSignature.with_instructions(ZERO_SHOT_INSTRUCTIONS)
)

# Define the path for the optimizations file
optimizations_json = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "optimizations_v4.json")
)

# Check if the optimizations file exists and load it
if os.path.exists(optimizations_json):
    logger.info(f"Loading optimizations from {optimizations_json}")
    with open(optimizations_json, "r") as f:
        optimizations = json.load(f)
        if "instructions" in optimizations:
            # Create a new program with the optimized instructions
            classifier_v4_program = dspy.Predict(
                signature=AgentClassificationSignature.with_instructions(
                    optimizations["instructions"]
                )
            )


def classifier_v4(chat_history: str) -> AgentClassificationSignature:
    result = classifier_v4_program(chat_history=chat_history)
    result.metrics = ClassifierMetrics(
        total_tokens=lm.total_tokens,
        prompt_tokens=lm.prompt_tokens,
        completion_tokens=lm.completion_tokens,
        latency_ms=lm.latency_ms,
    )

    # Log token usage when in debug mode
    if os.environ.get("TRIAGE_DEBUG") == "1":
        logger.debug(
            f"Token usage - Total: {lm.total_tokens}, "
            f"Prompt: {lm.prompt_tokens}, Completion: {lm.completion_tokens}"
        )
    return result


if __name__ == "__main__":
    load_dotenv()
    test_cases = [
        "User: Hello! How are you today?",
        "User: I need to pay my bill. Can you help me?",
        "User: What does my policy cover for water damage?",
        "User: I want to file a claim for my car accident yesterday.",
        "User: I've been trying to resolve this for weeks! I need to speak to a manager!",
    ]

    logger.info("Testing zero-shot classifier on example cases:")
    for test in test_cases:
        res = classifier_v4(chat_history=test)
        logger.info(f"Input: {test}\nClassified as: {res.target_agent}\n")
