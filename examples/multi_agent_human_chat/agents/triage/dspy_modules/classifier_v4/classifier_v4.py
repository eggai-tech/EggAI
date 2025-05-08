import os
from typing import Dict, Any

import dspy
from dotenv import load_dotenv
import json

from agents.triage.config import Settings
from agents.triage.models import formatted_agent_registry, TargetAgent, ClassifierMetrics, AGENT_REGISTRY
from libraries.dspy_set_language_model import dspy_set_language_model

settings = Settings()

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
ZERO_SHOT_INSTRUCTIONS = """
You are an intelligent classifier in a multi-agent insurance support system. Your task is to analyze the chat history and determine which specialized agent should handle the user's query.

## Available Target Agents:
""" + formatted_agent_registry() + """

## Classification Rules:
1. If the query is about bills, payments, invoices, refunds, or financial matters → BillingAgent
2. If the query is about policy details, coverage, terms, renewals, or documents → PolicyAgent
3. If the query is about filing a claim, claim status, or claim documentation → ClaimsAgent
4. If the query involves issues requiring escalation, speaking with managers, or technical problems → EscalationAgent
5. If the query is a greeting, casual conversation, or non-insurance related → ChattyAgent (fallback)

## Decision Process:
1. Analyze the entire chat history to understand context
2. Identify key terms and topics related to insurance
3. Match these topics to the most appropriate specialized agent
4. If multiple agents could handle the query, choose the one that best matches the primary concern
5. If the query contains no insurance-related content, route to ChattyAgent

Return only the name of the target agent without explanation.
"""

classifier_v4_program = dspy.Predict(signature=AgentClassificationSignature.with_instructions(ZERO_SHOT_INSTRUCTIONS))

# Define the path for the optimizations file
optimizations_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v4.json"))

# Check if the optimizations file exists and load it
if os.path.exists(optimizations_json):
    print(f"Loading optimizations from {optimizations_json}")
    with open(optimizations_json, 'r') as f:
        optimizations = json.load(f)
        if 'instructions' in optimizations:
            # Create a new program with the optimized instructions
            classifier_v4_program = dspy.Predict(
                signature=AgentClassificationSignature.with_instructions(optimizations['instructions'])
            )

def classifier_v4(chat_history: str) -> AgentClassificationSignature:
    result = classifier_v4_program(chat_history=chat_history)
    result.metrics = ClassifierMetrics(
        total_tokens=lm.total_tokens,
        prompt_tokens=lm.prompt_tokens,
        completion_tokens=lm.completion_tokens,
        latency_ms=lm.latency_ms,
    )
    return result


if __name__ == "__main__":
    load_dotenv()
    test_cases = [
        "User: Hello! How are you today?",
        "User: I need to pay my bill. Can you help me?",
        "User: What does my policy cover for water damage?",
        "User: I want to file a claim for my car accident yesterday.",
        "User: I've been trying to resolve this for weeks! I need to speak to a manager!"
    ]
    
    print("Testing zero-shot classifier on example cases:")
    for test in test_cases:
        res = classifier_v4(chat_history=test)
        print(f"Input: {test}\nClassified as: {res.target_agent}\n")
