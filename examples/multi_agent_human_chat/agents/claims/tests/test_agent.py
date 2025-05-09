import asyncio
import pytest
import dspy
import mlflow
import time
from uuid import uuid4
from datetime import datetime
from typing import List
from eggai import Agent, Channel
from ..agent import claims_agent, settings
from libraries.tracing import TracedMessage
from libraries.logger import get_console_logger
from libraries.dspy_set_language_model import dspy_set_language_model

logger = get_console_logger("claims_agent.tests")

# Configure language model based on settings with caching disabled for accurate metrics
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
logger.info(f"Using language model: {settings.language_model}")

test_cases = [
    {
        "chat_history": (
            "User: Hi, I'd like to check my claim status.\n"
            "ClaimsAgent: Sure! Could you please provide your claim number?\n"
            "User: It's 1001.\n"
        ),
        "expected_response": (
            "Your claim #1001 is currently 'In Review'. "
            "We estimate a payout of $2300.00 by 2025-05-15. "
            "We're still awaiting your repair estimates—please submit them at your earliest convenience."
        ),
        "chat_messages": [
            {"role": "User", "content": "Hi, I'd like to check my claim status."},
            {"role": "ClaimsAgent", "content": "Sure! Could you please provide your claim number?"},
            {"role": "User", "content": "It's 1001."},
        ]
    }
    # Other test cases temporarily disabled due to Kafka timeouts
    # Uncomment when Kafka issues are resolved
    # ,
    # {
    #     "chat_history": (
    #         "User: I need to file a new claim.\n"
    #         "ClaimsAgent: I'd be happy to help you file a new claim. Could you please provide your policy number and details about the incident?\n"
    #         "User: My policy number is A12345, and my car was damaged in a parking lot yesterday.\n"
    #     ),
    #     "expected_response": (
    #         "I've filed a new claim for your policy A12345."
    #     ),
    #     "chat_messages": [
    #         {"role": "User", "content": "I need to file a new claim."},
    #         {"role": "ClaimsAgent", "content": "I'd be happy to help you file a new claim. Could you please provide your policy number and details about the incident?"},
    #         {"role": "User", "content": "My policy number is A12345, and my car was damaged in a parking lot yesterday."},
    #     ]
    # },
    # {
    #     "chat_history": (
    #         "User: I need to update my address on my claim.\n"
    #         "ClaimsAgent: I can help with that. What is your claim number?\n"
    #         "User: Claim number 1002.\n"
    #     ),
    #     "expected_response": (
    #         "What is the new address you'd like to update on your claim?"
    #     ),
    #     "chat_messages": [
    #         {"role": "User", "content": "I need to update my address on my claim."},
    #         {"role": "ClaimsAgent", "content": "I can help with that. What is your claim number?"},
    #         {"role": "User", "content": "Claim number 1002."},
    #     ]
    # }
]

class ClaimsEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")

# Set up test agents and channels
test_agent = Agent("TestClaimsAgent")
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
    group_id="test_claims_agent_group"
)
async def _handle_response(event):
    logger.info(f"Received event: {event}")
    await _response_queue.put(event)

@pytest.mark.asyncio
async def test_claims_agent():
    # Configure MLflow tracking
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    mlflow.set_experiment("claims_agent_tests")
    with mlflow.start_run(run_name=f"claims_agent_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"):
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        await claims_agent.start()
        await test_agent.start()

        test_results = []
        evaluation_results = []

        # Send test cases one at a time to ensure proper matching
        for i, case in enumerate(test_cases):
            # Log the test case
            logger.info(f"Running test case {i+1}/{len(test_cases)}: {case['chat_messages'][-1]['content']}")
            
            connection_id = f"test-{i+1}"
            message_id = str(uuid4())
            
            # Capture test start time for latency measurement
            start_time = time.perf_counter()
            
            # Clear any existing responses in queue
            while not _response_queue.empty():
                try:
                    _response_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            # Simulate a claims request event
            await test_channel.publish(
                TracedMessage(
                    id=message_id,
                    type="claim_request",
                    source="TestClaimsAgent",
                    data={
                        "chat_messages": case["chat_messages"],
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
                
                while (time.perf_counter() - start_wait) < 30.0:  # 30-second total timeout
                    try:
                        event = await asyncio.wait_for(_response_queue.get(), timeout=2.0)
                        
                        # Check if this response matches our request and comes from ClaimsAgent
                        if event["data"].get("connection_id") == connection_id and event.get("source") == "ClaimsAgent":
                            matching_event = event
                            logger.info(f"Found matching response from ClaimsAgent for connection_id {connection_id}")
                            break
                        else:
                            # Log which agent is responding for debugging
                            source = event.get("source", "unknown")
                            logger.info(f"Received non-matching response from {source} for connection_id {event['data'].get('connection_id')}, waiting for ClaimsAgent with {connection_id}")
                    except asyncio.TimeoutError:
                        # Wait a little and try again
                        await asyncio.sleep(0.5)
                
                if not matching_event:
                    raise asyncio.TimeoutError(f"Timeout waiting for response with connection_id {connection_id}")
                    
                event = matching_event
                
                # Get connection ID and message from response
                response_connection_id = event["data"].get("connection_id")
                agent_response = event["data"].get("message")
                logger.info(f"Received response for test {i+1}: {agent_response[:100]}")
                
                # Calculate latency
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Response received in {latency_ms:.1f} ms")

                # Evaluate the response
                eval_model = dspy.asyncify(dspy.Predict(ClaimsEvaluationSignature))
                evaluation_result = await eval_model(
                    chat_history=case["chat_history"],
                    agent_response=agent_response,
                    expected_response=case["expected_response"],
                )
                
                # Track results for reporting
                test_result = {
                    "id": f"test-{i+1}",
                    "expected": case["expected_response"][:30] + "...",
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
                
                # Manual validation of critical elements in response
                logger.info(f"Performing additional validation for test case {i+1}")
                
                # Check claim number is in response
                claim_number = None
                if "1001" in case["expected_response"]:
                    claim_number = "1001"
                elif "1002" in case["expected_response"]:
                    claim_number = "1002"
                elif "1003" in case["expected_response"]:
                    claim_number = "1003"
                
                if claim_number:
                    assert claim_number in agent_response, f"Expected claim number {claim_number} missing from response"
                
                # Check amount format is correct if it's a claim status check (case 0)
                if i == 0:  # This is the claim status check for claim 1001
                    assert "$2300" in agent_response or "$2,300" in agent_response, "Expected amount $2300 missing from response"
                    # Check date format is YYYY-MM-DD
                    assert "2025-05-15" in agent_response, "Expected date 2025-05-15 missing from response"
                
                # Assertions using LLM evaluation
                assert evaluation_result.judgment, (
                    f"Test case {i+1} failed: " + evaluation_result.reasoning
                )
                assert 0.8 <= evaluation_result.precision_score <= 1.0, (
                    f"Test case {i+1} precision score {evaluation_result.precision_score} out of range [0.8,1.0]"
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout: No response received within timeout period for test {i+1}")
                pytest.fail(f"Timeout: No response received within timeout period for test {i+1}")

        # Check if we have results
        if not evaluation_results:
            logger.error("No evaluation results collected! Test failed to match responses to requests.")
            pytest.fail("No evaluation results collected. Check logs for details.")
            
        # Calculate overall metrics
        overall_precision = sum(e.precision_score for e in evaluation_results) / len(evaluation_results)
        mlflow.log_metric("overall_precision", overall_precision)
        
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
        logger.info("\n=== Claims Agent Test Results ===\n")
        logger.info(table)
        logger.info("\n==================================\n")
        
        # Log report to MLflow
        mlflow.log_text(table, "test_results.md")