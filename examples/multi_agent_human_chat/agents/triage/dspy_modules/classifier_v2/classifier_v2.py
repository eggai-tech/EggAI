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


classifier_v2_program = dspy.Predict(signature=AgentClassificationSignature.with_instructions(
    """
    As a classifier, you have to classify and route messages to appropriate target agents based on context in a multi-agent insurance support system.
    
    Available Target Agents: 
    """ + formatted_agent_registry() + """
    
    Classification Rules:
    1. If the query is about bills, payments, invoices, payment methods, refunds, or billing settings → BillingAgent
    2. If the query is about policy details, coverage, terms, renewals, or documents → PolicyAgent
    3. If the query is about filing a claim, claim status, claim appeals, or claim documentation → ClaimsAgent
    4. If the query involves issues requiring escalation or speaking with managers → EscalationAgent
    5. If the query is a greeting, casual conversation, or non-insurance related → ChattyAgent
    
    Important Disambiguation Rules:
    - ALL questions about claims processing, claim appeals process, or claim disputes should go to ClaimsAgent, NOT PolicyAgent
    - Refund requests or refund status inquiries go to BillingAgent, NOT ClaimsAgent
    - ALL billing settings including paperless billing and automatic payments go to BillingAgent, NOT PolicyAgent
    - ANY mention of "appeal" or "appeal process" related to claims should ALWAYS go to ClaimsAgent
    
    Fallback Rules: Route to ChattyAgent if the query is not insurance-related.
    """
))

optimizations_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "optimizations_v2.json"))
if os.path.exists(optimizations_json):
    print(f"Loading optimizations from {optimizations_json}")
    classifier_v2_program.load(optimizations_json)


def classifier_v2(chat_history: str) -> AgentClassificationSignature:
    result = classifier_v2_program(chat_history=chat_history)
    result.metrics = ClassifierMetrics(
        total_tokens=lm.total_tokens,
        prompt_tokens=lm.prompt_tokens,
        completion_tokens=lm.completion_tokens,
        latency_ms=lm.latency_ms,
    )
    return result


if __name__ == "__main__":
    load_dotenv()
    res = classifier_v2(
        chat_history="User: hello!",
    )
    print(res.target_agent)
