"""Test utilities for billing agent tests."""

import asyncio
import time
from datetime import datetime

import dspy
import mlflow

from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.tests.utils")


def create_message_list(user_messages, agent_responses=None):
    """Create a list of chat messages from user messages and agent responses."""
    if agent_responses is None:
        agent_responses = []
        
    messages = []
    # Interleave user messages and agent responses
    for i, user_msg in enumerate(user_messages):
        messages.append({"role": "User", "content": user_msg})
        if i < len(agent_responses):
            messages.append({"role": "BillingAgent", "content": agent_responses[i]})
    return messages


def create_conversation_string(messages):
    """Create a conversation string from message list."""
    conversation = ""
    for msg in messages:
        conversation += f"{msg['role']}: {msg['content']}\n"
    return conversation


class BillingEvaluationSignature(dspy.Signature):
    """DSPy signature for LLM-based evaluation of billing agent responses."""
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


def get_test_cases():
    """Get standard test cases for billing agent tests."""
    # Define base test cases
    test_cases = [
        {
            "policy_number": "B67890",
            "expected_response": "Your next payment of $300.00 is due on 2025-03-15.",
            "user_messages": [
                "Hi, I'd like to know my next billing date.",
                "It's B67890."
            ],
            "agent_responses": [
                "Sure! Please provide your policy number."
            ]
        },
        {
            "policy_number": "A12345",
            "expected_response": "Your current amount due is $120.00 with a due date of 2025-02-01.",
            "user_messages": [
                "How much do I owe on my policy?",
                "A12345"
            ],
            "agent_responses": [
                "I'd be happy to check that for you. Could you please provide your policy number?"
            ]
        },
        {
            "policy_number": "C24680",
            "expected_response": "Your billing cycle has been successfully changed to Monthly.",
            "user_messages": [
                "I want to change my billing cycle.",
                "C24680"
            ],
            "agent_responses": [
                "I can help you with that. May I have your policy number please?"
            ]
        }
    ]
    
    # Process test cases to add derived fields
    for case in test_cases:
        # Create message list
        case["chat_messages"] = create_message_list(
            case["user_messages"], 
            case.get("agent_responses")
        )
        
        # Create conversation string
        case["chat_history"] = create_conversation_string(case["chat_messages"])
        
    return test_cases


async def wait_for_agent_response(response_queue, connection_id: str, timeout: float = 30.0) -> dict:
    """Wait for a response from the agent with matching connection ID."""
    start_wait = time.perf_counter()
    
    # Clear any existing responses in queue
    while not response_queue.empty():
        try:
            response_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
    # Keep checking for matching responses
    while (time.perf_counter() - start_wait) < timeout:
        try:
            event = await asyncio.wait_for(response_queue.get(), timeout=2.0)
            
            # Check if this response matches our request and comes from BillingAgent
            if (event["data"].get("connection_id") == connection_id and 
                event.get("source") == "BillingAgent"):
                return event
        except asyncio.TimeoutError:
            # Wait a little and try again
            await asyncio.sleep(0.5)
    
    raise asyncio.TimeoutError(f"Timeout waiting for response with connection_id {connection_id}")


class MLflowTracker:
    """Context manager for MLflow tracking."""
    
    def __init__(self, experiment_name, run_name=None, params=None):
        self.experiment_name = experiment_name
        self.run_name = run_name
        self.params = params
        
    def __enter__(self):
        mlflow.set_experiment(self.experiment_name)
        if self.run_name is None:
            self.run_name = f"billing_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        
        self.run = mlflow.start_run(run_name=self.run_name)
        
        if self.params:
            for key, value in self.params.items():
                mlflow.log_param(key, value)
                
        return self.run
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        mlflow.end_run()
        return False  # Don't suppress exceptions


def setup_mlflow_tracking(experiment_name, run_name=None, params=None):
    """Create an MLflow tracking context manager."""
    return MLflowTracker(experiment_name, run_name, params)


async def evaluate_response_with_llm(chat_history, expected_response, agent_response, dspy_lm):
    """Evaluate agent response against the expected response using LLM."""
    # Evaluate using LLM
    eval_model = dspy.asyncify(dspy.Predict(BillingEvaluationSignature))
    with dspy.context(lm=dspy_lm):
        evaluation_result = await eval_model(
            chat_history=chat_history,
            agent_response=agent_response,
            expected_response=expected_response,
        )
    
    return evaluation_result