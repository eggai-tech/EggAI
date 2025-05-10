import asyncio
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import mlflow
import pandas as pd
import pytest
from faststream.kafka import KafkaMessage

from agents.audit.agent import MESSAGE_CATEGORIES, audit_message
from agents.audit.config import Settings
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

logger = get_console_logger("audit_agent.tests")
settings = Settings()

@pytest.fixture(scope="function", autouse=True)
async def mock_channel_publish():
    fut = asyncio.Future()
    fut.set_result(None)
    
    with patch('eggai.channel.Channel.publish', return_value=fut) as _:
        yield
        
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

@pytest.fixture
def traced_message_factory():
    def create(message_type, source, test_id=0):
        return TracedMessage(
            id=str(uuid4()),
            type=message_type,
            source=source,
            data={"test_id": test_id}
        )
    return create

@pytest.fixture
def mock_kafka_message_factory():
    def create(channel="test_channel"):
        msg = MagicMock(spec=KafkaMessage)
        msg.path = {"channel": channel}
        return msg
    return create

@pytest.fixture
def mock_tracer():
    mock_span = MagicMock()
    with patch('agents.audit.agent.tracer.start_as_current_span') as mock_tracer:
        mock_tracer.return_value.__enter__.return_value = mock_span
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=None)
        yield mock_span

def setup_mlflow_run(experiment_name, run_name_prefix, params=None):
    mlflow.set_experiment(experiment_name)
    run_name = f"{run_name_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run = mlflow.start_run(run_name=run_name)
    
    if params:
        for key, value in params.items():
            mlflow.log_param(key, value)
            
    return run

def generate_report(results, test_cases, total_time, metrics=None):
    correct_count = sum(1 for r in results if r.get("correct") == "✓")
    accuracy = correct_count / len(test_cases) if test_cases else 0
    
    if metrics:
        for name, value in metrics.items():
            mlflow.log_metric(name, value)
            
    mlflow.log_metric("total_processing_time_ms", total_time)
    
    try:
        results_table = pd.DataFrame(results).to_markdown()
    except ImportError:
        results_table = pd.DataFrame(results).to_string()
        
    summary = f"""
- Messages processed: {len(test_cases)}
- Total time: {total_time:.2f} ms
"""
    
    if any("correct" in r for r in results):
        summary += f"- Correct categorizations: {correct_count}\n"
        summary += f"- Accuracy: {accuracy:.2%}\n"
        mlflow.log_metric("categorization_accuracy", accuracy)
    
    return f"""
## Audit Agent Test Results

### Summary
{summary}

### Detailed Results
{results_table}
"""

@pytest.mark.asyncio
async def test_audit_agent_categorization_and_publishing(traced_message_factory, mock_kafka_message_factory, mock_tracer):
    test_cases = [
        {"type": "agent_message", "source": "ChatAgent", "expected_category": "User Communication"},
        {"type": "billing_request", "source": "BillingSystem", "expected_category": "Billing"},
        {"type": "policy_request", "source": "PolicyAdmin", "expected_category": "Policies"},
        {"type": "escalation_request", "source": "Manager", "expected_category": "Escalation"},
        {"type": "triage_request", "source": "SupportAgent", "expected_category": "Triage"},
        {"type": "unknown_type", "source": "ExternalSystem", "expected_category": "Other"},
    ]
    
    with setup_mlflow_run("audit_agent_tests", "audit_agent_test", {
        "test_type": "message_categorization_with_spans",
        "agent": "audit"
    }):
        start_time = time.perf_counter()
        results = []
        
        for i, test_case in enumerate(test_cases):
            message_type = test_case["type"]
            source = test_case["source"]
            expected_category = test_case["expected_category"]
            
            traced_message = traced_message_factory(message_type, source, i)
            message_id = traced_message.id
            kafka_msg = mock_kafka_message_factory(f"test_channel_{i}")
            
            case_start = time.perf_counter()
            result = await audit_message(traced_message, kafka_msg)
            case_time = (time.perf_counter() - case_start) * 1000
            
            mlflow.log_metric(f"message_{i+1}_processing_time_ms", case_time)
            mlflow.log_param(f"message_{i+1}_type", message_type)
            
            mock_tracer.set_attribute.assert_any_call("audit.channel", f"test_channel_{i}")
            mock_tracer.set_attribute.assert_any_call("audit.message_type", message_type)
            mock_tracer.set_attribute.assert_any_call("audit.source", source)
            mock_tracer.set_attribute.assert_any_call("audit.category", expected_category)
            
            actual_category = MESSAGE_CATEGORIES.get(message_type, "Other")
            is_correct = actual_category == expected_category
            assert is_correct, f"Expected '{message_type}' to be categorized as '{expected_category}', got '{actual_category}'"
            
            mlflow.log_metric(f"message_{i+1}_correct_category", 1.0 if is_correct else 0.0)
            assert result == traced_message, "Audit function should return the same message it received"
            
            with patch('eggai.channel.Channel.publish') as mock_publish:
                await audit_message(traced_message, kafka_msg)
                
                assert mock_publish.called, "Should publish audit event"
                
                call_args = mock_publish.call_args[0][0]
                assert call_args.type == "audit_log", "Should publish an audit_log event"
                assert call_args.source == "AuditAgent", "Should come from AuditAgent"
                assert call_args.data["message_id"] == str(message_id), "Should reference original message"
            
            results.append({
                "message_id": message_id,
                "type": message_type,
                "source": source,
                "channel": f"test_channel_{i}",
                "expected": expected_category,
                "actual": actual_category,
                "time_ms": f"{case_time:.2f}",
                "spans_set": mock_tracer.set_attribute.call_count,
                "correct": "✓" if is_correct else "✗"
            })
        
        total_time = (time.perf_counter() - start_time) * 1000
        report = generate_report(results, test_cases, total_time, {
            "messages_processed": len(test_cases),
            "test_passed": 1.0
        })
        
        logger.info(f"\n=== Audit Agent Test Results ===\n{report}\n")
        mlflow.log_text(report, "audit_test_results.md")

@pytest.mark.asyncio
async def test_audit_agent_error_handling(traced_message_factory, mock_kafka_message_factory):
    error_cases = [
        {"case": "null_message", "description": "Passing None as message"},
        {"case": "exception_during_processing", "description": "Raising exception during processing"},
        {"case": "invalid_kafka_message", "description": "No channel in Kafka message"}
    ]
    
    with setup_mlflow_run("audit_agent_error_tests", "audit_error_test", {
        "test_type": "error_handling"
    }):
        start_time = time.perf_counter()
        results = []
        
        # Test 1: Null message handling
        kafka_msg = mock_kafka_message_factory("test_channel")
        case_start = time.perf_counter()
        
        with patch('eggai.channel.Channel.publish') as mock_publish:
            result = await audit_message(None, kafka_msg)
            case_time = (time.perf_counter() - case_start) * 1000
            
            assert result is None, "Should return None when given None"
            assert mock_publish.called, "Should publish null message audit event"
            
            call_args = mock_publish.call_args[0][0]
            assert call_args.type == "audit_log", "Should publish an audit_log event"
            assert call_args.source == "AuditAgent", "Should come from AuditAgent"
            assert call_args.data["message_type"] == "null", "Should be a null message type"
            assert "null_message_" in call_args.data["message_id"], "Should have null message ID"
            assert call_args.data["category"] == "Error", "Should be categorized as Error"
        
        mlflow.log_metric("null_message_handled", 1.0)
        mlflow.log_metric("null_message_audit_published", 1.0)
        mlflow.log_metric("null_message_time_ms", case_time)
        
        results.append({
            "case": "null_message",
            "time_ms": f"{case_time:.2f}",
            "result": "Handled correctly and audit event published"
        })
        
        # Test 2: Message causing AttributeError
        case_start = time.perf_counter()
        problematic_message = "This will cause an AttributeError because it's not a TracedMessage or dict"
        
        result = await audit_message(problematic_message, kafka_msg)
        case_time = (time.perf_counter() - case_start) * 1000
        
        assert result == problematic_message, "Should return original problematic message"
        mlflow.log_metric("exception_handled", 1.0)
        mlflow.log_metric("exception_time_ms", case_time)
        
        results.append({
            "case": "exception_during_processing",
            "time_ms": f"{case_time:.2f}",
            "result": "Handled correctly"
        })
        
        # Test 3: Invalid Kafka message
        case_start = time.perf_counter()
        invalid_kafka = MagicMock(spec=KafkaMessage)
        invalid_kafka.path = {}  # No channel key
        
        message = traced_message_factory("test_type", "test_source")
        
        result = await audit_message(message, invalid_kafka)
        case_time = (time.perf_counter() - case_start) * 1000
        
        assert result == message, "Should handle missing channel key"
        mlflow.log_metric("invalid_kafka_handled", 1.0)
        mlflow.log_metric("invalid_kafka_time_ms", case_time)
        
        results.append({
            "case": "invalid_kafka_message",
            "time_ms": f"{case_time:.2f}",
            "result": "Handled correctly"
        })
        
        total_time = (time.perf_counter() - start_time) * 1000
        report = generate_report(results, error_cases, total_time, {
            "error_cases_tested": len(error_cases),
            "error_tests_passed": 1.0
        })
        
        logger.info(f"\n=== Audit Agent Error Handling Results ===\n{report}\n")
        mlflow.log_text(report, "audit_error_handling_results.md")