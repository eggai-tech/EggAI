import asyncio
import pytest
import dspy
import mlflow
import time
import json
from uuid import uuid4
from datetime import datetime
from typing import List
from eggai import Agent, Channel
from ..agent import ticketing_agent as escalation_agent, settings
from libraries.tracing import TracedMessage
from libraries.logger import get_console_logger
from libraries.dspy_set_language_model import dspy_set_language_model

logger = get_console_logger("escalation_agent.tests")

# Configure language model based on settings with caching disabled for accurate metrics
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
logger.info(f"Using language model: {settings.language_model}")

test_cases = [
    {
        "chat_messages": [
            {
                "role": "User",
                "content": "My issue wasn't resolved by PoliciesAgent. I'm still having trouble.",
            },
            {
                "role": "EscalationAgent",
                "content": "Certainly. Could you describe the issue in more detail?",
            },
            {
                "role": "User",
                "content": "It's about my billing setup. The website keeps throwing an error.",
            },
        ],
        "expected_meaning": (
            "The agent asks the user to provide contact information."
        ),
    },
    {
        "chat_messages": [
            {
                "role": "User",
                "content": "I need to speak with a manager immediately.",
            },
            {
                "role": "EscalationAgent",
                "content": "I understand you'd like to speak with a manager. Could you briefly explain what issue you're experiencing?",
            },
            {
                "role": "User",
                "content": "I've been double-charged for my insurance policy.",
            },
        ],
        "expected_meaning": (
            "The agent creates a ticket for the billing department."
        ),
    },
    {
        "chat_messages": [
            {
                "role": "User",
                "content": "I'm having technical issues with the website.",
            },
            {
                "role": "EscalationAgent", 
                "content": "I'm sorry to hear you're experiencing technical issues. Could you provide more details about what specifically is happening?",
            },
            {
                "role": "User",
                "content": "The payment page won't load. I've tried three different browsers.",
            },
        ],
        "expected_meaning": (
            "The agent creates a technical support ticket."
        ),
    }
]


class EscalationEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_meaning: str = dspy.InputField(desc="Expected meaning of the response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


test_agent = Agent("TestEscalationAgent")
test_channel = Channel("agents")
human_channel = Channel("human")

_response_queue = asyncio.Queue()


def _markdown_table(rows: List[List[str]], headers: List[str]) -> str:
    """Generate a markdown table from rows and headers."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells):
        return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    lines = [_fmt_row(headers), sep]
    lines += [_fmt_row(r) for r in rows]
    return "\n".join(lines)


@test_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda event: event.get("type") == "agent_message",
    auto_offset_reset="latest",
    group_id="test_escalation_agent_group"
)
async def _handle_response(event):
    logger.info(f"Received event: {event}")
    await _response_queue.put(event)


@pytest.mark.asyncio
async def test_escalation_agent():
    # Configure MLflow tracking
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    mlflow.set_experiment("escalation_agent_tests")
    with mlflow.start_run(run_name=f"escalation_agent_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"):
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        await escalation_agent.start()
        await test_agent.start()

        test_results = []
        evaluation_results = []
        
        # Send test cases one at a time to ensure proper matching
        for i, case in enumerate(test_cases):
            # Log the test case
            logger.info(f"Running test case {i+1}/{len(test_cases)}")
            formatted_chat = "\n".join([f"{m['role']}: {m['content']}" for m in case["chat_messages"]])
            logger.info(f"Chat history: {formatted_chat[:50]}...")
            
            connection_id = f"test-{i+1}"
            message_id = str(uuid4())
            session_id = f"session_{i+1}"
            
            # Capture test start time for latency measurement
            start_time = time.perf_counter()
            
            # Clear any existing responses in queue
            while not _response_queue.empty():
                try:
                    _response_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
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
                    },
                )
            )

            try:
                # Wait for response with timeout
                logger.info(f"Waiting for response for test case {i+1} with connection_id {connection_id}")
                
                # Keep checking for matching responses
                start_wait = time.perf_counter()
                matching_event = None
                
                while (time.perf_counter() - start_wait) < 10.0:  # 10-second total timeout
                    try:
                        event = await asyncio.wait_for(_response_queue.get(), timeout=2.0)
                        
                        # Check if this response matches our request and comes from TicketingAgent
                        if event["data"].get("connection_id") == connection_id and event.get("source") == "TicketingAgent":
                            matching_event = event
                            logger.info(f"Found matching response from TicketingAgent for connection_id {connection_id}")
                            break
                        else:
                            # Log which agent is responding for debugging
                            source = event.get("source", "unknown")
                            logger.info(f"Received non-matching response from {source} for connection_id {event['data'].get('connection_id')}, waiting for TicketingAgent with {connection_id}")
                    except asyncio.TimeoutError:
                        # Wait a little and try again
                        await asyncio.sleep(0.5)
                
                if not matching_event:
                    raise asyncio.TimeoutError(f"Timeout waiting for response with connection_id {connection_id}")
                    
                event = matching_event
                
                # Get agent response from event
                agent_response = event["data"].get("message")
                logger.info(f"FULL RESPONSE: {agent_response}")
                
                # Calculate latency
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Response received in {latency_ms:.1f} ms")

                # Evaluate the response
                eval_model = dspy.asyncify(dspy.Predict(EscalationEvaluationSignature))
                evaluation_result = await eval_model(
                    chat_history="\n".join([f"{m['role']}: {m['content']}" for m in case["chat_messages"]]),
                    agent_response=agent_response,
                    expected_meaning=case["expected_meaning"],
                )
                
                # Track results for reporting
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
                
                # Log to MLflow
                mlflow.log_metric(f"precision_case_{i+1}", evaluation_result.precision_score)
                mlflow.log_metric(f"latency_case_{i+1}", latency_ms)
                
                # Assertions
                assert evaluation_result.judgment, (
                    f"Test case {i+1} failed: " + evaluation_result.reasoning
                )
                assert 0.7 <= evaluation_result.precision_score <= 1.0, (
                    f"Test case {i+1} precision score {evaluation_result.precision_score} out of range [0.7,1.0]"
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout: No response received within timeout period for test {i+1}")
                pytest.fail(f"Timeout: No response received within timeout period for test {i+1}")

        # Generate report
        headers = ["ID", "Expected", "Response", "Latency", "LLM ✓", "LLM Prec", "Reasoning"]
        rows = [
            [
                r["id"], r["expected"], r["response"], r["latency"],
                r["judgment"], r["precision"], r["reasoning"],
            ]
            for r in test_results
        ]
        table = _markdown_table(rows, headers)
        
        # Print report
        logger.info("\n=== Escalation Agent Test Results ===\n")
        logger.info(table)
        logger.info("\n====================================\n")
        
        # Log report to MLflow
        mlflow.log_text(table, "test_results.md")