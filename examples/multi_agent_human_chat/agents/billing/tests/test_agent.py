import asyncio
import time
from datetime import datetime
from typing import List
from uuid import uuid4

import dspy
import mlflow
import pytest
from eggai import Agent, Channel

from agents.billing.dspy_modules.billing import billing_optimized_dspy
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

from ..agent import billing_agent, settings

logger = get_console_logger("billing_agent.tests")

# Configure language model based on settings with caching disabled for accurate metrics
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
logger.info(f"Using language model: {settings.language_model}")

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


# Test cases for the BillingAgent
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

class BillingEvaluationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


test_agent = Agent("TestBillingAgent")
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
    group_id="test_billing_agent_group"
)
async def _handle_response(event):
    logger.info(f"Received event: {event}")
    await _response_queue.put(event)


import re
from typing import List, Tuple


def get_amount_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate money amount matching between expected and actual responses."""
    try:
        # Extract amount in various formats ($300.00, $300, etc.)
        expected_amount_match = re.search(r'\$(\d+(?:\.\d+)?)', expected)
        expected_amount = expected_amount_match.group(1) if expected_amount_match else None
        
        if not expected_amount:
            return (0.5, True) if "$" in actual else (0.0, False)
            
        # Try to find the same amount in various formats
        amount_patterns = [
            fr'\${expected_amount}',  # $300.00
            fr'\$\s*{expected_amount}',  # $ 300.00
            fr'\${expected_amount.split(".")[0]}',  # $300
            fr'\${int(float(expected_amount)):,}',  # $300 with commas if needed
        ]
        
        # Check each pattern
        for pattern in amount_patterns:
            if re.search(pattern, actual):
                return (1.0, True)
                
        # If amount not found but $ is present, partial credit
        return (0.5, True) if "$" in actual else (0.0, True)
    except (IndexError, ValueError):
        # If $ is present in both, partial credit
        return (0.5, True) if "$" in actual else (0.0, True)


def get_date_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate date matching between expected and actual responses."""
    date_formats = ["2025-02-01", "2025-03-15", "2025-12-01"]
    
    for date in date_formats:
        if date not in expected:
            continue
            
        # Full date exact match
        if date in actual:
            return (1.0, True)
        
        # Extract components for partial matching
        year, month, day = date.split("-")
        
        # Various date formats
        date_patterns = [
            f"{month}/{day}/{year}",  # 03/15/2025
            f"{month}-{day}-{year}",  # 03-15-2025
            f"{month}.{day}.{year}",  # 03.15.2025
            f"{year}-{month}",        # 2025-03 (partial)
            f"{month}/{year}",        # 03/2025 (partial)
            f"{month} {year}",        # March 2025
        ]
        
        # Check for any date pattern
        for pattern in date_patterns:
            if pattern in actual:
                return (0.8, True)  # Almost full credit for alternative formats
                
        # Check for month names if numerical didn't match
        month_names = {
            "01": ["january", "jan"],
            "02": ["february", "feb"],
            "03": ["march", "mar"],
            "04": ["april", "apr"],
            "05": ["may"],
            "06": ["june", "jun"],
            "07": ["july", "jul"],
            "08": ["august", "aug"],
            "09": ["september", "sep", "sept"],
            "10": ["october", "oct"],
            "11": ["november", "nov"],
            "12": ["december", "dec"]
        }
        
        if month in month_names:
            for month_name in month_names[month]:
                if month_name in actual and year in actual:
                    return (0.7, True)  # Good credit for month name + year
            
        # Basic year matching
        if year in actual:
            return (0.3, True)  # Minimal credit for just the year
    
    return (0.0, False)  # No date match found


def get_status_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate status matching between expected and actual responses."""
    if "status is" not in expected and "'status':" not in expected:
        return (0.0, False)
        
    try:
        # Extract status using different patterns
        status_patterns = [
            r"status is ['\"]([^'\"]+)['\"]",  # status is 'Pending'
            r"status:? ['\"]?([^'\",.]+)['\"]?",  # status: Pending or status: "Pending"
            r"status:? ([^,\.]+)",  # status: Pending (no quotes)
            r"your status is ([^,\.]+)",  # your status is Pending
            r"current status is ([^,\.]+)",  # current status is Pending
        ]
        
        expected_status = None
        for pattern in status_patterns:
            match = re.search(pattern, expected)
            if match:
                expected_status = match.group(1).strip().lower()
                break
        
        if expected_status:
            # Check for status in actual response
            if expected_status in actual:
                return (1.0, True)
            elif "status" in actual:
                # Check if any word after "status" matches expected status approximately
                status_words = re.findall(r"status\W+(\w+)", actual)
                for word in status_words:
                    if (word.lower() == expected_status or 
                        word.lower() in expected_status or 
                        expected_status in word.lower()):
                        return (0.8, True)
                return (0.5, True)  # Status mentioned but different
        else:
            # Couldn't extract expected status, give partial credit if status mentioned
            if "status" in actual:
                return (0.5, True)
    except Exception:
        # Fallback - give partial credit if status is mentioned
        if "status" in actual:
            return (0.5, True)
            
    return (0.0, False)  # No status match


def get_billing_cycle_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate billing cycle matching between expected and actual responses."""
    if "billing cycle" not in expected:
        return (0.0, False)
        
    # Try to extract cycle type
    cycle_types = ["annual", "monthly", "quarterly", "bi-monthly", "weekly"]
    expected_cycle = None
    
    # Find which cycle type is in expected
    for cycle in cycle_types:
        if cycle in expected.lower():
            expected_cycle = cycle
            break
    
    # Check for cycle in actual
    if "billing cycle" in actual and expected_cycle and expected_cycle in actual:
        return (1.0, True)  # Full match - both billing cycle and type
    elif "billing cycle" in actual:
        return (0.8, True)  # Billing cycle mentioned but type may differ
    elif "cycle" in actual and expected_cycle and expected_cycle in actual:
        return (0.7, True)  # Cycle type matches but not specifically "billing cycle"
    elif "cycle" in actual:
        return (0.5, True)  # Just "cycle" mentioned
    elif expected_cycle and expected_cycle in actual:
        return (0.3, True)  # Just cycle type mentioned
        
    return (0.0, False)  # No billing cycle match


def get_format_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate format consistency between expected and actual responses."""
    format_score = 0.0
    format_checks = 0
    
    # Date format consistency
    if "2025" in expected and "2025" in actual:
        format_checks += 1
        # Check if using YYYY-MM-DD format consistently
        if re.search(r'20\d\d-\d\d-\d\d', expected) and re.search(r'20\d\d-\d\d-\d\d', actual):
            format_score += 1.0
        else:
            format_score += 0.5  # Date present but format differs
    
    # Dollar format consistency
    if "$" in expected and "$" in actual:
        format_checks += 1
        # Check if using $X.XX format
        if re.search(r'\$\d+\.\d\d', expected) and re.search(r'\$\d+\.\d\d', actual):
            format_score += 1.0
        else:
            format_score += 0.5  # Dollar present but format differs
    
    # Add format score if we checked anything
    if format_checks > 0:
        return (format_score / format_checks, True)
        
    return (0.0, False)  # No format checks performed


def precision_metric(expected_str: str, actual_str: str) -> float:
    """Calculate precision score by comparing expected and predicted responses."""
    expected = expected_str.lower()
    actual = actual_str.lower()
    
    score = 0.0
    check_count = 0
    
    # Run all evaluations
    evaluations = [
        get_amount_score(expected, actual),
        get_date_score(expected, actual),
        get_status_score(expected, actual),
        get_billing_cycle_score(expected, actual),
        get_format_score(expected, actual)
    ]
    
    # Aggregate results
    for eval_score, eval_performed in evaluations:
        if eval_performed:
            score += eval_score
            check_count += 1
    
    # Calculate overall score
    if check_count == 0:
        return 0.0
        
    return score / check_count


async def wait_for_agent_response(connection_id: str, timeout: float = 30.0) -> dict:
    """Wait for a response from the agent with matching connection ID."""
    start_wait = time.perf_counter()
    
    # Clear any existing responses in queue
    while not _response_queue.empty():
        try:
            _response_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
    # Keep checking for matching responses
    while (time.perf_counter() - start_wait) < timeout:
        try:
            event = await asyncio.wait_for(_response_queue.get(), timeout=2.0)
            
            # Check if this response matches our request and comes from BillingAgent
            if (event["data"].get("connection_id") == connection_id and 
                event.get("source") == "BillingAgent"):
                logger.info(f"Found matching response for connection_id {connection_id}")
                return event
            else:
                # Log which agent is responding for debugging
                source = event.get("source", "unknown")
                logger.info(f"Received non-matching response from {source}")
        except asyncio.TimeoutError:
            # Wait a little and try again
            await asyncio.sleep(0.5)
    
    raise asyncio.TimeoutError(f"Timeout waiting for response with connection_id {connection_id}")


async def evaluate_response(case: dict, agent_response: str):
    """Evaluate agent response against the expected response."""
    # Calculate precision score
    precision_score = precision_metric(case["expected_response"], agent_response)
    
    # Evaluate using LLM
    eval_model = dspy.asyncify(dspy.Predict(BillingEvaluationSignature))
    evaluation_result = await eval_model(
        chat_history=case["chat_history"],
        agent_response=agent_response,
        expected_response=case["expected_response"],
    )
    
    return {
        "precision_score": precision_score,
        "llm_evaluation": evaluation_result
    }


def log_test_metrics(case_index: int, precision_score: float, 
                    llm_score: float, latency_ms: float):
    """Log metrics for a test case to MLflow."""
    mlflow.log_metric(f"precision_case_{case_index+1}", llm_score)
    mlflow.log_metric(f"calc_precision_case_{case_index+1}", precision_score)
    mlflow.log_metric(f"latency_case_{case_index+1}", latency_ms)


def generate_test_report(test_results):
    """Generate a markdown report from test results."""
    headers = ["ID", "Policy", "Expected", "Response", "Latency", 
               "LLM ✓", "LLM Prec", "Calc Prec", "Reasoning"]
    rows = [
        [
            r["id"], r["policy"], r["expected"], r["response"], r["latency"],
            r["judgment"], r["precision"], r["calc_precision"], r["reasoning"],
        ]
        for r in test_results
    ]
    return _markdown_table(rows, headers)


@pytest.mark.asyncio
async def test_billing_agent():
    """Test the billing agent with Kafka integration"""
    
    # Configure MLflow tracking
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    mlflow.set_experiment("billing_agent_tests")
    run_name = f"billing_agent_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        await billing_agent.start()
        await test_agent.start()

        test_results = []
        evaluation_results = []

        # Process test cases
        for i, case in enumerate(test_cases):
            logger.info(f"Running test case {i+1}/{len(test_cases)}: {case['chat_messages'][-1]['content']}")
            
            connection_id = f"test-{i+1}"
            message_id = str(uuid4())
            
            # Capture test start time for latency measurement
            start_time = time.perf_counter()
            
            # Publish test message
            await test_channel.publish(
                TracedMessage(
                    id=message_id,
                    type="billing_request",
                    source="TestBillingAgent",
                    data={
                        "chat_messages": case["chat_messages"],
                        "connection_id": connection_id,
                        "message_id": message_id,
                    },
                )
            )
            
            try:
                # Wait for agent response
                event = await wait_for_agent_response(connection_id)
                
                # Extract and log response
                agent_response = event["data"].get("message")
                logger.info(f"Received response: {agent_response[:100]}...")
                
                # Calculate latency
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Response time: {latency_ms:.1f} ms")
                
                # Log test details
                logger.info(f"Test case {i+1} - Policy: {case['policy_number']}")
                logger.info(f"Expected: {case['expected_response']}")
                logger.info(f"Actual: {agent_response}")
                
                # Evaluate response
                evaluation = await evaluate_response(case, agent_response)
                precision_score = evaluation["precision_score"]
                evaluation_result = evaluation["llm_evaluation"]
                
                logger.info(f"Precision score: {precision_score:.4f}")
                
                # Track results
                test_result = {
                    "id": f"test-{i+1}",
                    "policy": case["policy_number"],
                    "expected": case["expected_response"][:30] + "...",
                    "response": agent_response[:30] + "...",
                    "latency": f"{latency_ms:.1f} ms",
                    "judgment": "✔" if evaluation_result.judgment else "✘",
                    "precision": f"{evaluation_result.precision_score:.2f}",
                    "calc_precision": f"{precision_score:.2f}",
                    "reasoning": (evaluation_result.reasoning or "")[:30] + "..."
                }
                test_results.append(test_result)
                
                evaluation_results.append({
                    "evaluation": evaluation_result,
                    "calculated_precision": precision_score
                })
                
                # Log metrics
                log_test_metrics(i, precision_score, evaluation_result.precision_score, latency_ms)
                
                # Verify test passed
                assert 0.7 <= precision_score <= 1.0, (
                    f"Test case {i+1} precision score {precision_score} out of range [0.7,1.0]"
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response for test {i+1}")
                pytest.fail(f"Timeout waiting for response for test {i+1}")

        # Verify results were collected
        if not evaluation_results:
            pytest.fail("No evaluation results collected")
            
        # Calculate and log overall metrics
        overall_llm_precision = sum(e["evaluation"].precision_score for e in evaluation_results) / len(evaluation_results)
        overall_calculated_precision = sum(e["calculated_precision"] for e in evaluation_results) / len(evaluation_results)
        mlflow.log_metric("overall_llm_precision", overall_llm_precision)
        mlflow.log_metric("overall_calculated_precision", overall_calculated_precision)
        
        # Generate and log report
        report = generate_test_report(test_results)
        logger.info(f"\n=== Billing Agent Test Results ===\n{report}\n")
        mlflow.log_text(report, "test_results.md")


def generate_module_test_report(test_results):
    """Generate a markdown report from module test results."""
    headers = ["ID", "Policy", "Expected", "Response", "Latency", "Precision", "Result"]
    rows = [
        [
            r["id"], r["policy"], r["expected"], r["response"], r["latency"],
            r["precision"], r["result"]
        ]
        for r in test_results
    ]
    return _markdown_table(rows, headers)


@pytest.mark.asyncio
async def test_billing_dspy_module():
    """A direct test of the billing agent that calls the DSPy module without Kafka."""
    # Configure MLflow tracking
    mlflow.set_experiment("billing_agent_module_tests")
    run_name = f"billing_module_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    
    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        test_results = []
        
        # Process each test case
        for i, case in enumerate(test_cases):
            logger.info(f"Running test case {i+1}/{len(test_cases)}: {case['chat_messages'][-1]['content']}")
            
            conversation_string = case["chat_history"]
            policy_number = case["policy_number"]
            
            # Measure performance
            start_time = time.perf_counter()
            agent_response = billing_optimized_dspy(chat_history=conversation_string)
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(f"Response time: {latency_ms:.1f} ms")
            logger.info(f"Agent response: {agent_response}")
            
            # Evaluate response
            precision_score = precision_metric(case["expected_response"], agent_response)
            
            # Log details
            logger.info(f"Test case {i+1} - Policy: {policy_number}")
            logger.info(f"Expected: {case['expected_response']}")
            logger.info(f"Actual: {agent_response}")
            logger.info(f"Precision score: {precision_score:.4f}")
            
            # Track results
            test_result = {
                "id": f"test-{i+1}",
                "policy": policy_number,
                "expected": case["expected_response"][:50] + "...",
                "response": agent_response[:50] + "...",
                "latency": f"{latency_ms:.1f} ms",
                "precision": f"{precision_score:.2f}",
                "result": "PASS" if precision_score >= 0.7 else "FAIL"
            }
            test_results.append(test_result)
            
            # Log metrics
            mlflow.log_metric(f"precision_case_{i+1}", precision_score)
            mlflow.log_metric(f"latency_case_{i+1}", latency_ms)
            
            # Verify test passed
            assert 0.7 <= precision_score <= 1.0, (
                f"Test case {i+1} precision score {precision_score} out of range [0.7,1.0]"
            )
            
        # Calculate and log overall metrics
        overall_precision = sum(float(r["precision"]) for r in test_results) / len(test_results)
        mlflow.log_metric("overall_precision", overall_precision)
        
        # Generate and log report
        report = generate_module_test_report(test_results)
        logger.info(f"\n=== Billing Module Test Results ===\n{report}\n")
        mlflow.log_text(report, "module_test_results.md")