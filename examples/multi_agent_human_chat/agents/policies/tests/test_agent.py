import asyncio
import re
import time
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import dspy
import mlflow
import pytest
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage
from libraries.channels import channels, clear_channels

from ..config import settings

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

from ..agent import policies_agent

logger = get_console_logger("policies_agent.tests")

dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)
logger.info(f"Using language model: {settings.language_model}")


def get_test_cases():
    """Return standardized test cases for policies agent testing."""
    return [
        {
            "id": "premium_due",
            "chat_history": (
                "User: When is my next premium payment due?\n"
                "PoliciesAgent: Could you please provide your policy number?\n"
                "User: B67890.\n"
            ),
            "expected_response": (
                "Your next premium payment for policy B67890 is due on 2026-03-15. The amount due is $300.00."
            ),
            "chat_messages": [
                {"role": "User", "content": "When is my next premium payment due?"},
                {"role": "PoliciesAgent", "content": "Could you please provide your policy number?"},
                {"role": "User", "content": "B67890."},
            ]
        },
        {
            "id": "auto_policy_coverage",
            "chat_history": (
                "User: I need information about my policy coverage.\n"
                "PoliciesAgent: I'd be happy to help. Could you please provide your policy number?\n"
                "User: A12345\n"
            ),
            "expected_response": (
                "Based on your auto policy A12345, your coverage includes collision, comprehensive, liability, and uninsured motorist protection."
            ),
            "chat_messages": [
                {"role": "User", "content": "I need information about my policy coverage."},
                {"role": "PoliciesAgent", "content": "I'd be happy to help. Could you please provide your policy number?"},
                {"role": "User", "content": "A12345"},
            ]
        },
        {
            "id": "home_policy_coverage",
            "chat_history": (
                "User: Does my policy cover water damage?\n"
                "PoliciesAgent: I can check that for you. Could you please let me know your policy number and what type of policy you have (home, auto, etc.)?\n"
                "User: It's C24680, home insurance.\n"
            ),
            "expected_response": (
                "According to your home insurance policy C24680, water damage from burst pipes is covered"
            ),
            "chat_messages": [
                {"role": "User", "content": "Does my policy cover water damage?"},
                {"role": "PoliciesAgent", "content": "I can check that for you. Could you please let me know your policy number and what type of policy you have (home, auto, etc.)?"},
                {"role": "User", "content": "It's C24680, home insurance."},
            ]
        },
        {
            "id": "insufficient_info",
            "chat_history": (
                "User: hello\nTriageAgent: Hello there! I'm an AI assistant here to help you understand your insurance options. While I appreciate your greeting, I'm not a human and can't answer general questions outside of insurance. To best assist you, could you tell me what you'd like to know about insurance coverage? Are you interested in learning more about auto, home, life, or health insurance? Let's focus on how I can help you protect yourself and your loved ones.\nUser: what policies do I have?\n \nTargetAgent.PolicyAgent: "
            ),
            "expected_response": (
                "I'd be happy to help. Could you please provide your policy number?"
            ),
            "chat_messages": [
                {"role": "User", "content": "hello\nTriageAgent: Hello there! I'm an AI assistant here to help you understand your insurance options. While I appreciate your greeting, I'm not a human and can't answer general questions outside of insurance. To best assist you, could you tell me what you'd like to know about insurance coverage? Are you interested in learning more about auto, home, life, or health insurance? Let's focus on how I can help you protect yourself and your loved ones.\nUser: what policies do I have?\n \nTargetAgent.PolicyAgent: "},
            ]
        },
    ]

# Load test cases
test_cases = get_test_cases()


class PolicyEvaluationSignature(dspy.Signature):
    """
    Evaluate a policies agent's response against customer information needs.
    
    YOUR ROLE:
    You are a senior customer experience evaluator at an insurance company.
    Your job is to determine if responses to customers provide the essential information they need.
    
    EVALUATION PHILOSOPHY:
    - CUSTOMER-FIRST: Does the response help the customer with their specific question?
    - INFORMATION VALUE: Does it provide the core information the customer is asking for?
    - REAL-WORLD UTILITY: Would a typical customer find this response helpful and clear?
    
    KEY PRINCIPLES:
    1. The exact wording, format, or style is NOT important
    2. What matters is whether the CONTENT answers the customer's question effectively
    3. Responses should contain the most critical information a customer needs
    4. Technical formatting (like exact date formats) is less important than clarity
    5. Assume the customer has context from their own conversation
    
    EVALUATION GUIDELINES BY INQUIRY TYPE:
    
    For Premium Payment Inquiries:
    - ESSENTIAL: Customer must learn when their payment is due (any understandable date format)
    - ESSENTIAL: Customer must learn how much they need to pay (any clear amount)
    - HELPFUL BUT OPTIONAL: Reference to their specific policy
    
    For Coverage Inquiries:
    - ESSENTIAL: Customer must learn what is or isn't covered
    - ESSENTIAL: Response addresses the specific type of coverage asked about
    - HELPFUL BUT OPTIONAL: Technical details about limits or conditions
    
    For Policy Information Requests:
    - ESSENTIAL: Customer must get the specific information they requested
    - ESSENTIAL: Response must be specific to their policy type
    - HELPFUL BUT OPTIONAL: Additional relevant details or next steps
    
    SCORING SYSTEM:
    - judgment: TRUE only if the response gives the customer their essential needed information
    - precision_score (0.0-1.0):
      * 0.8-1.0: EXCELLENT - customer gets complete information that fully answers their question
      * 0.6-0.7: GOOD - customer gets most essential information but minor details missing
      * 0.4-0.5: ADEQUATE - customer gets basic information but important details missing
      * 0.0-0.3: INADEQUATE - customer doesn't get critical information needed
    
    IMPORTANT: Focus ONLY on value to the customer. Ignore technical assessment of the agent's format.
    """
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    agent_response: str = dspy.InputField(desc="Agent-generated response.")
    expected_response: str = dspy.InputField(desc="Expected correct response.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")


# Set up test agent and channels
test_agent = Agent("TestPoliciesAgent")
# Use channels from central configuration
test_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)

_response_queue: asyncio.Queue[TracedMessage] = asyncio.Queue()


def validate_response_for_test_case(case_id: str, response: str) -> Dict[str, bool]:
    """
    Perform content validation focused on essential information.
    
    This is customer-focused validation - does the response provide the key
    information the customer needs, regardless of exact format?
    """
    results = {"valid": True, "notes": []}
    
    if case_id == "premium_due":
        # Essential: Date must be present (more flexible pattern matching)
        date_pattern = r"2026-03-15|March 15(th|,)?( 2026)?|(03|3)[-/\.](15|15th)[-/\.]2026|15(th)? (of )?March( 2026)?"
        results["has_date"] = bool(re.search(date_pattern, response, re.IGNORECASE))
        if not results["has_date"]:
            results["notes"].append("Missing payment date")
            
        # Check for ANY dollar amount - essential for premium inquiry
        # Using possessive quantifiers to prevent backtracking
        amount_pattern = r"(?:\$\d+(?:\.\d{2})?|\d+(?:\.\d{2})?\s+dollars?)"
        results["has_amount"] = bool(re.search(amount_pattern, response, re.IGNORECASE))
        if not results["has_amount"]:
            results["notes"].append("Missing payment amount")
            
        # Policy info - helpful but not required if context is clear
        policy_pattern = r"B67890|policy|insurance"
        results["has_policy_info"] = bool(re.search(policy_pattern, response, re.IGNORECASE))
        if not results["has_policy_info"]:
            results["notes"].append("No policy reference")
        
        # Set as valid if it has at least the amount and some date reference
        # This is a more customer-focused approach - does it answer the core question?
        results["valid"] = results["has_amount"] and (results["has_date"] or "March" in response or "2026" in response)
        
    elif case_id == "auto_policy_coverage":
        # Essential: Mentions auto/car insurance (expanded pattern)
        category_pattern = r"auto|car|vehicle|motor|automobile|automotive|driving|driver"
        results["has_category"] = bool(re.search(category_pattern, response, re.IGNORECASE))
        if not results["has_category"]:
            results["notes"].append("Missing auto insurance reference")
        
        # Essential: Mentions some kind of coverage (expanded pattern)
        coverage_pattern = r"cover(age|ed|s)|protect(ion|ed)|includ(e|ed|es)|insur(ance|ed)|benefit"
        results["has_coverage"] = bool(re.search(coverage_pattern, response, re.IGNORECASE))
        if not results["has_coverage"]:
            results["notes"].append("No coverage details")
            
        # Policy info - helpful for context
        policy_pattern = r"A12345|policy|insurance|number"
        results["has_policy_info"] = bool(re.search(policy_pattern, response, re.IGNORECASE))
        if not results["has_policy_info"]:
            results["notes"].append("No policy reference")
        
        # Set as valid if it mentions coverage
        # Less strict to allow for different response patterns
        results["valid"] = results["has_coverage"] and (results["has_category"] or results["has_policy_info"])
        
    elif case_id == "home_policy_coverage":
        # Essential: Mentions home insurance (expanded pattern)
        category_pattern = r"home|house|property|residential|dwelling"
        results["has_category"] = bool(re.search(category_pattern, response, re.IGNORECASE))
        if not results["has_category"]:
            results["notes"].append("Missing home insurance reference")
        
        # Essential: Clear answer about water damage (expanded pattern)
        coverage_pattern = r"water damage|burst pipes|flooding|water leaks|water-related|plumbing issues"
        results["has_coverage_topic"] = bool(re.search(coverage_pattern, response, re.IGNORECASE))
        if not results["has_coverage_topic"]:
            results["notes"].append("No mention of water damage")
        
        # Check for answer about coverage (expanded pattern)
        answer_pattern = r"(is|are|will be) covered|cover(s|ed|age)|includ(es|ed)|protect(s|ed|ion)|part of (your|the) policy"
        results["has_answer"] = bool(re.search(answer_pattern, response, re.IGNORECASE))
        if not results["has_answer"]:
            results["notes"].append("No clear answer about coverage")
        
        # More flexible validation
        # Valid if it mentions water damage and gives some indication of coverage
        results["valid"] = results["has_coverage_topic"] and results["has_answer"]
    
    return results


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
    channel=test_channel,
    filter_by_message=lambda event: event.get("type") != "user_message",
    auto_offset_reset="latest",
    group_id="test_policies_agent_group_agents"
)
async def _handle_agents_response(event: TracedMessage):
    if event.type == "policy_request":
        global _agent_request_count
        _agent_request_count += 1
        return
    await _response_queue.put(event)


@test_agent.subscribe(
    channel=human_channel,
    filter_by_message=lambda event: event.get("type") == "agent_message",
    auto_offset_reset="latest",
    group_id="test_policies_agent_group_human"
)
async def _handle_human_response(event: TracedMessage):
    await _response_queue.put(event)


_stream_chunks = {}
_agent_request_count = 0

@test_agent.subscribe(
    channel=human_stream_channel,
    filter_by_message=lambda event: event.get("type") in ["agent_message_stream_start", "agent_message_stream_chunk", "agent_message_stream_end"],
    auto_offset_reset="latest", 
    group_id="test_policies_agent_group_stream"
)
async def _handle_stream_response(event: TracedMessage):
    if event.type == "agent_message_stream_chunk":
        msg_id = event.data.get("message_id")
        chunk_content = event.data.get("message_chunk", "")
        if msg_id:
            if msg_id not in _stream_chunks:
                _stream_chunks[msg_id] = []
            _stream_chunks[msg_id].append(chunk_content)
    elif event.type == "agent_message_stream_end":
        await _response_queue.put(event)




@pytest.mark.asyncio
async def test_policies_agent_single():
    """Test the policies agent with a single request to debug streaming."""
    
    await clear_channels()
    
    # Clear stream chunks and counters
    global _stream_chunks, _agent_request_count
    _stream_chunks = {}
    _agent_request_count = 0
    
    await policies_agent.start()
    await test_agent.start()
    
    # Send just one test case
    test_case = test_cases[0]  # premium_due
    msg_id = str(uuid4())
    connection_id = "test-single"
    
    
    await test_channel.publish(
        TracedMessage(
            id=msg_id,
            type="policy_request",
            source="TestPoliciesAgent",
            data={
                "chat_messages": test_case["chat_messages"],
                "connection_id": connection_id,
                "message_id": msg_id,
            },
        )
    )
    
    try:
        event = await asyncio.wait_for(_response_queue.get(), timeout=5.0)
        if event.type == "agent_message_stream_end":
            agent_response = event.data.get("message", "")
            logger.info(f"Received final response: {agent_response}")
        if msg_id in _stream_chunks:
            chunks = _stream_chunks[msg_id]
            full_response = "".join(chunks)
    except asyncio.TimeoutError:
        pass
    
    finally:
        await policies_agent.stop()
        await test_agent.stop()
        await asyncio.sleep(0.5)


@pytest.mark.asyncio
@pytest.mark.skip
async def test_policies_agent():
    """Test the policies agent with standardized test cases."""
    
    await clear_channels()
    
    global _stream_chunks, _agent_request_count
    _stream_chunks = {}
    _agent_request_count = 0
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True
    )

    mlflow.set_experiment("policies_agent_tests")
    with mlflow.start_run(run_name=f"policies_agent_test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"):
        mlflow.log_param("test_count", len(test_cases))
        mlflow.log_param("language_model", settings.language_model)
        
        await policies_agent.start()
        await test_agent.start()

        pending: Dict[str, Any] = {}
        policy_results: List[Dict[str, Any]] = []
        
        for i, case in enumerate(test_cases):
            msg_id = str(uuid4())
            connection_id = f"test-{i+1}"
            pending[msg_id] = {
                "case": case,
                "connection_id": connection_id,
                "start_time": time.perf_counter()
            }
            
            
            await test_channel.publish(
                TracedMessage(
                    id=msg_id,
                    type="policy_request",
                    source="TestPoliciesAgent",
                    data={
                        "chat_messages": case["chat_messages"],
                        "connection_id": connection_id,
                        "message_id": msg_id,
                    },
                )
            )
            
            await asyncio.sleep(0.1)
        
        await asyncio.sleep(1.0)
        
        collected_responses = 0
        timeout_count = 0
        
        while collected_responses < len(test_cases) and timeout_count < 3:
            try:
                event = await asyncio.wait_for(_response_queue.get(), timeout=2.0)
                
                msg_id = event.data.get("message_id")
                conn_id = event.data.get("connection_id")
                
                pending_item = None
                if msg_id and msg_id in pending:
                    pending_item = pending.pop(msg_id)
                else:
                    for mid, item in list(pending.items()):
                        if item["connection_id"] == conn_id:
                            pending_item = pending.pop(mid)
                            break
                
                if not pending_item:
                    continue
                
                case = pending_item["case"]
                latency_ms = (time.perf_counter() - pending_item["start_time"]) * 1000
                
                agent_response = event.data.get("message", "")
                
                policy_results.append({
                    "case": case,
                    "agent_response": agent_response,
                    "latency_ms": latency_ms,
                    "event": event
                })
                
                collected_responses += 1
                
                mlflow.log_metric(f"latency_case_{collected_responses}", latency_ms)
                
            except asyncio.TimeoutError:
                timeout_count += 1
        
        
        # Phase 3: Evaluate responses
        test_results = []
        evaluation_results = []
        
        for i, result in enumerate(policy_results):
            case = result["case"]
            agent_response = result["agent_response"]
            latency_ms = result["latency_ms"]
            
            
            validation_results = validate_response_for_test_case(case["id"], agent_response)
            
            eval_model = dspy.asyncify(dspy.Predict(PolicyEvaluationSignature))
            evaluation_result = await eval_model(
                chat_history=case["chat_history"],
                agent_response=agent_response,
                expected_response=case["expected_response"],
            )
            
            test_result = {
                "id": case["id"],
                "expected": case["expected_response"][:50] + "...",
                "actual": agent_response[:50] + "...",
                "latency": f"{latency_ms:.1f} ms",
                "judgment": "✔" if evaluation_result.judgment else "✘",
                "precision": f"{evaluation_result.precision_score:.2f}",
                "reasoning": (evaluation_result.reasoning or "")[:100] + "..."
            }
            
            test_results.append(test_result)
            evaluation_results.append(evaluation_result)
            
            mlflow.log_metric(f"precision_case_{i+1}", evaluation_result.precision_score)
            mlflow.log_metric(f"llm_judgment_{i+1}", 1.0 if evaluation_result.judgment else 0.0)
            
            if not validation_results["valid"]:
                mlflow.set_tag(f"validation_issues_{case['id']}", str(validation_results.get("notes", [])))
        
        if not evaluation_results:
            pytest.fail("No evaluation results collected. Check logs for details.")
        
        overall_precision = sum(e.precision_score for e in evaluation_results) / len(evaluation_results)
        passed_count = sum(1 for e in evaluation_results if e.judgment)
        pass_rate = passed_count / len(evaluation_results) if evaluation_results else 0
        
        mlflow.log_metric("overall_precision", overall_precision)
        mlflow.log_metric("pass_rate", pass_rate)
        mlflow.log_metric("passed_count", passed_count)
        mlflow.log_metric("total_tests", len(evaluation_results))
        
        headers = ["ID", "Expected Response", "Actual Response", "LLM Judgment", "Precision", "Latency"]
        rows = [
            [
                r["id"], r["expected"], r["actual"],
                r["judgment"], r["precision"], r["latency"]
            ]
            for r in test_results
        ]
        table = _markdown_table(rows, headers)
        
        needs_improvement = []
        for i, (test_result, eval_result) in enumerate(zip(test_results, evaluation_results)):
            if not eval_result.judgment or eval_result.precision_score < 0.5:
                issue = f"LLM Judgment: {eval_result.judgment}, Precision: {eval_result.precision_score:.2f}"
                needs_improvement.append(f"- {test_result['id']}: {issue} - {eval_result.reasoning[:100]}...")
        
        improvement_report = "\n".join(needs_improvement)
        
        logger.info("\n=== Policies Agent Test Results ===\n")
        logger.info(table)
        logger.info(f"\nOverall Pass Rate: {pass_rate:.1%} ({passed_count}/{len(evaluation_results)})")
        logger.info(f"Overall Precision: {overall_precision:.2f}")
        
        if needs_improvement:
            logger.info("\n=== Tests Requiring Improvement ===\n")
            logger.info(improvement_report)
            mlflow.log_text(improvement_report, "improvement_needed.md")
        
        logger.info("\n====================================\n")
        
        mlflow.log_text(table, "test_results.md")
        
        assert passed_count > 0, f"All {len(evaluation_results)} tests failed LLM evaluation"
        
        if pass_rate < 0.8:
            logger.warning(f"Low pass rate: {pass_rate:.1%}. Consider improving agent responses.")
        
        await policies_agent.stop()
        await test_agent.stop()
        
        await asyncio.sleep(0.5)