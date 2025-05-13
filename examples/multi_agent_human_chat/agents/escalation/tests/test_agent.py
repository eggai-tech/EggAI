"""
Tests for the Escalation Agent.

This module contains tests for the escalation agent functionality.
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import dspy
import mlflow
import pytest
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport

from agents.escalation.config import settings
from libraries.kafka_transport import create_kafka_transport

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

from ..agent import ticketing_agent as escalation_agent
from ..types import ChatMessage

# Configure logger
logger = get_console_logger("escalation_agent.tests")

# Configure language model based on settings
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
logger.info(f"Using language model: {settings.language_model}")

# Test agent setup
test_agent = Agent("TestEscalationAgent")
test_channel = Channel("agents")
human_channel = Channel("human")
_response_queue = asyncio.Queue()


def create_test_cases() -> List[Dict]:
    """Create test cases for the escalation agent."""
    return [
        {
            "chat_messages": [
                {"role": "User", "content": "My issue wasn't resolved by PoliciesAgent. I'm still having trouble."},
                {"role": "TicketingAgent", "content": "Certainly. Could you describe the issue in more detail?"},
                {"role": "User", "content": "It's about my billing setup. The website keeps throwing an error."},
            ],
            "expected_meaning": "The agent asks the user to provide contact information."
        },
        {
            "chat_messages": [
                {"role": "User", "content": "I need to speak with a manager immediately."},
                {"role": "TicketingAgent", "content": "I understand you'd like to speak with a manager. Could you briefly explain what issue you're experiencing?"},
                {"role": "User", "content": "I've been double-charged for my insurance policy."},
            ],
            "expected_meaning": "The agent creates a ticket for the billing department."
        },
        {
            "chat_messages": [
                {"role": "User", "content": "I'm having technical issues with the website."},
                {"role": "TicketingAgent", "content": "I'm sorry to hear you're experiencing technical issues. Could you provide more details about what specifically is happening?"},
                {"role": "User", "content": "The payment page won't load. I've tried three different browsers."},
            ],
            "expected_meaning": "The agent creates a technical support ticket."
        }
    ]


# DSPy Signature for evaluating responses
class EscalationEvaluationSignature(dspy.Signature):
    """DSPy signature for evaluating escalation agent responses."""
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_meaning: str = dspy.InputField(desc="Expected meaning of the response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


def generate_report(test_results: List[Dict], headers: List[str]) -> str:
    """Generate a markdown table report from test results."""
    widths = [len(h) for h in headers]
    for row in test_results:
        row_values = [row.get(h.lower().replace(" ", "_"), "") for h in headers]
        for i, cell in enumerate(row_values):
            widths[i] = max(widths[i], len(str(cell)))

    def format_row(cells):
        return "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

    separator = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    lines = [format_row(headers), separator]
    
    for row in test_results:
        row_values = [row.get(h.lower().replace(" ", "_"), "") for h in headers]
        lines.append(format_row(row_values))
        
    return "\n".join(lines)


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Convert chat messages to conversation string."""
    return "\n".join([f"{m['role']}: {m['content']}" for m in chat_messages])


@test_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda event: event.get("type") == "agent_message",
    auto_offset_reset="latest",
    group_id="test_escalation_agent_group"
)
async def handle_agent_response(event):
    """Handle agent responses during testing."""
    logger.info(f"Received event: {event}")
    await _response_queue.put(event)


async def wait_for_agent_response(connection_id: str, timeout: float = 10.0) -> Optional[Dict]:
    """Wait for a response from the agent with the specified connection ID."""
    # Clear existing messages
    while not _response_queue.empty():
        try:
            _response_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    
    # Wait for matching response
    start_wait = time.perf_counter()
    while (time.perf_counter() - start_wait) < timeout:
        try:
            event = await asyncio.wait_for(_response_queue.get(), timeout=2.0)
            
            if (event["data"].get("connection_id") == connection_id and 
                event.get("source") == "TicketingAgent"):
                logger.info(f"Found matching response for connection_id {connection_id}")
                return event
            else:
                source = event.get("source", "unknown")
                logger.info(f"Received non-matching response from {source}")
        except asyncio.TimeoutError:
            await asyncio.sleep(0.5)
    
    return None


async def evaluate_response(chat_history: str, agent_response: str, expected_meaning: str) -> Dict:
    """Evaluate agent response against expected meaning."""
    eval_model = dspy.asyncify(dspy.Predict(EscalationEvaluationSignature))
    return await eval_model(
        chat_history=chat_history,
        agent_response=agent_response,
        expected_meaning=expected_meaning
    )


def setup_mlflow():
    """Configure MLflow for test tracking."""
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )
    
    mlflow.set_experiment("escalation_agent_tests")
    run_name = f"escalation_agent_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    return mlflow.start_run(run_name=run_name)


@pytest.mark.asyncio
async def test_escalation_agent():
    """Test the escalation agent functionality."""
    test_cases = create_test_cases()
    
    with setup_mlflow():
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        await escalation_agent.start()
        await test_agent.start()

        test_results = []
        evaluation_results = []
        
        # Test each case
        for i, case in enumerate(test_cases):
            logger.info(f"Running test case {i+1}/{len(test_cases)}")
            
            # Setup test data
            connection_id = f"test-{i+1}"
            message_id = str(uuid4())
            session_id = f"session_{i+1}"
            
            # Log test details
            chat_history = get_conversation_string(case["chat_messages"])
            logger.info(f"Chat history: {chat_history[:50]}...")
            
            # Measure performance
            start_time = time.perf_counter()
            
            # Send test request
            await test_channel.publish(
                TracedMessage(
                    id=message_id,
                    type="ticketing_request",
                    source="TestEscalationAgent",
                    data={
                        "chat_messages": case["chat_messages"],
                        "session": session_id,
                        "connection_id": connection_id,
                        "message_id": message_id,
                    }
                )
            )

            try:
                # Wait for response
                event = await wait_for_agent_response(connection_id)
                if not event:
                    raise asyncio.TimeoutError(f"Timeout waiting for response for test {i+1}")
                
                # Process response
                agent_response = event["data"].get("message")
                logger.info(f"Response: {agent_response}")
                
                # Calculate latency
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Response time: {latency_ms:.1f} ms")

                # Evaluate response
                evaluation_result = await evaluate_response(
                    chat_history=chat_history,
                    agent_response=agent_response,
                    expected_meaning=case["expected_meaning"]
                )
                
                # Track results
                test_result = {
                    "id": f"test-{i+1}",
                    "expected": case["expected_meaning"][:30] + ("..." if len(case["expected_meaning"]) > 30 else ""),
                    "response": agent_response[:30] + "...",
                    "latency": f"{latency_ms:.1f} ms",
                    "judgment": "✔" if evaluation_result.judgment else "✘",
                    "precision": f"{evaluation_result.precision_score:.2f}",
                    "reasoning": (evaluation_result.reasoning or "")[:30] + "..."
                }
                test_results.append(test_result)
                evaluation_results.append(evaluation_result)
                
                # Log metrics
                mlflow.log_metric(f"precision_case_{i+1}", evaluation_result.precision_score)
                mlflow.log_metric(f"latency_case_{i+1}", latency_ms)
                
                # Verify expectations with more resilient thresholds
                assert evaluation_result.judgment or evaluation_result.precision_score >= 0.7, (
                    f"Test case {i+1} failed: {evaluation_result.reasoning}"
                )
                assert 0.6 <= evaluation_result.precision_score <= 1.0, (
                    f"Test case {i+1} precision score {evaluation_result.precision_score} out of range [0.6,1.0]"
                )
                
            except asyncio.TimeoutError as e:
                logger.error(f"Timeout: {str(e)}")
                pytest.fail(f"Timeout: {str(e)}")

        # Generate and log report
        headers = ["ID", "Expected", "Response", "Latency", "LLM ✓", "LLM Prec", "Reasoning"]
        report = generate_report(test_results, headers)
        
        logger.info(f"\n=== Escalation Agent Test Results ===\n{report}\n")
        mlflow.log_text(report, "test_results.md")