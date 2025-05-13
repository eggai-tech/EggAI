"""Tests for the Audit Agent."""
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import mlflow
import pandas as pd
import pytest
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport

from agents.audit.config import settings
from libraries.kafka_transport import create_kafka_transport

eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

from agents.audit.agent import MESSAGE_CATEGORIES, audit_agent, audit_message
from agents.audit.types import AuditCategory
from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

logger = get_console_logger("audit_agent.tests")

test_agent = Agent("TestAuditAgent")
human_channel = Channel(channels.human)
agents_channel = Channel(channels.agents)
audit_logs_channel = Channel(channels.audit_logs)
response_queue = asyncio.Queue()


@test_agent.subscribe(
    channel=audit_logs_channel,
    filter_by_message=lambda event: event.get("type") == "audit_log",
    auto_offset_reset="latest",
    group_id="test_audit_agent_group"
)
async def _handle_audit_response(event: TracedMessage):
    await response_queue.put(event)


@pytest.fixture(scope="module", autouse=True)
async def setup_agents():
    from libraries.tracing import init_telemetry
    init_telemetry(app_name="test_audit_agent")
    
    await test_agent.start()
    await audit_agent.start()
    
    await asyncio.sleep(2)
    
    yield
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def wait_for_audit_response(timeout=10.0) -> Optional[TracedMessage]:
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        if not response_queue.empty():
            return await response_queue.get()
        await asyncio.sleep(0.5)
    raise asyncio.TimeoutError(f"No message received after {timeout} seconds")


async def send_message_and_wait(
    message: TracedMessage,
    channel: Channel,
    timeout=10.0
) -> tuple[Dict, Optional[TracedMessage], float]:
    case_start = time.perf_counter()
    
    while not response_queue.empty():
        await response_queue.get()
    
    await channel.publish(message)
    
    try:
        audit_response = await wait_for_audit_response(timeout)
        case_time = (time.perf_counter() - case_start) * 1000
        
        assert audit_response.type == "audit_log", f"Expected message type 'audit_log', got '{audit_response.type}'"
        assert audit_response.source == "AuditAgent", f"Expected source 'AuditAgent', got '{audit_response.source}'"
        
        if audit_response.data.get("message_id"):
            assert audit_response.data.get("message_id") == str(message.id)
        
        channel_id = "human" if channel == human_channel else "agents" if channel == agents_channel else "unknown"
        result = {
            "message_id": message.id,
            "type": message.type,
            "source": message.source,
            "channel": channel_id,
            "actual": audit_response.data.get("category"),
            "time_ms": f"{case_time:.2f}"
        }
        
        return result, audit_response, case_time
        
    except asyncio.TimeoutError:
        case_time = (time.perf_counter() - case_start) * 1000
        channel_id = "human" if channel == human_channel else "agents" if channel == agents_channel else "unknown"
        return {
            "message_id": message.id,
            "type": message.type,
            "source": message.source,
            "channel": channel_id,
            "error": "Timeout waiting for response",
            "time_ms": f"{case_time:.2f}"
        }, None, case_time


def log_metrics(results: List[Dict], test_cases: Dict[str, AuditCategory], total_time: float) -> None:
    mlflow.log_metric("messages_processed", len(results))
    mlflow.log_metric("total_time_ms", total_time)
    
    if results and "time_ms" in results[0]:
        latencies = [float(r["time_ms"]) for r in results]
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else avg_latency
        
        mlflow.log_metric("avg_latency_ms", avg_latency)
        mlflow.log_metric("min_latency_ms", min_latency)
        mlflow.log_metric("max_latency_ms", max_latency)
        mlflow.log_metric("p95_latency_ms", p95_latency)
    
    try:
        results_df = pd.DataFrame(results)
        report = f"## {len(results)} messages processed in {total_time:.2f}ms\n\n"
        report += results_df.to_markdown()
        mlflow.log_text(report, "audit_report.md")
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)


@pytest.mark.asyncio
async def test_audit_agent_basic():
    message_type = "agent_message"
    source = "ChatAgent" 
    expected_category = "User Communication"
    mock_kafka = type('MockKafkaMessage', (), {'path': {'channel': 'human'}})()
    
    with mlflow.start_run(run_name=f"audit_basic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
        start_time = time.perf_counter()
        
        message_id = str(uuid4())
        traced_message = TracedMessage(
            id=message_id,
            type=message_type,
            source=source,
            data={"test_id": 1, "timestamp": datetime.now().isoformat()}
        )
        
        direct_result = await audit_message(traced_message, mock_kafka)
        assert direct_result is not None, "Direct audit_message call failed"
        
        result, response, case_time = await send_message_and_wait(
            traced_message, human_channel, timeout=15.0
        )
        
        total_time = (time.perf_counter() - start_time) * 1000
        mlflow.log_metric("total_time_ms", total_time)
        mlflow.log_metric("processing_time_ms", case_time)
        
        assert direct_result is not None, "Direct audit_message call failed"
        
        if response:
            assert response.data.get("category") == expected_category, \
                f"Expected category '{expected_category}', got '{response.data.get('category')}'"


@pytest.mark.asyncio
async def test_audit_agent_message_types():
    with mlflow.start_run(run_name=f"audit_all_types_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
        start_time = time.perf_counter()
        results = []
        
        for message_type, expected_category in MESSAGE_CATEGORIES.items():
            source = f"Test{message_type.title().replace('_', '')}"
            channel = human_channel if message_type == "agent_message" else agents_channel
            channel_name = "human" if channel == human_channel else "agents"
            mock_kafka = type('MockKafkaMessage', (), {'path': {'channel': channel_name}})()
            
            try:
                message_id = str(uuid4())
                traced_message = TracedMessage(
                    id=message_id,
                    type=message_type,
                    source=source,
                    data={"test_id": len(results) + 1, "timestamp": datetime.now().isoformat()}
                )
                
                direct_result = await audit_message(traced_message, mock_kafka)
                assert direct_result is not None, f"Direct call failed for {message_type}"
                
                result = {
                    "message_id": message_id,
                    "type": message_type,
                    "source": source,
                    "channel": channel_name,
                    "expected": expected_category,
                    "time_ms": "0.00"
                }
                
                asyncio.create_task(channel.publish(traced_message))
                
                results.append(result)
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing {message_type}: {e}")
                results.append({
                    "message_id": str(uuid4()),
                    "type": message_type,
                    "source": source,
                    "channel": channel_name,
                    "expected": expected_category,
                    "error": str(e),
                    "time_ms": "0.00"
                })
        
        total_time = (time.perf_counter() - start_time) * 1000
        log_metrics(results, MESSAGE_CATEGORIES, total_time)
        
        assert len(results) == len(MESSAGE_CATEGORIES), "Not all message types were processed"


@pytest.mark.asyncio
async def test_audit_agent_error_handling():
    with mlflow.start_run(run_name=f"audit_error_handling_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
        message_type = "unknown_message_type"
        source = "TestSource"
        expected_category = "Other"
        mock_kafka = type('MockKafkaMessage', (), {'path': {'channel': 'agents'}})()
        
        message_id = str(uuid4())
        traced_message = TracedMessage(
            id=message_id,
            type=message_type,
            source=source,
            data={"test_id": 1, "timestamp": datetime.now().isoformat()}
        )
        
        direct_result = await audit_message(traced_message, mock_kafka)
        assert direct_result is not None, "Direct call failed for unknown message type"
        
        result, response, case_time = await send_message_and_wait(
            traced_message, agents_channel, timeout=10.0
        )
        
        if response:
            actual_category = response.data.get("category")
            mlflow.log_param("actual_category", actual_category)
            mlflow.log_param("expected_category", expected_category)
            
            assert actual_category == expected_category, \
                f"Expected category '{expected_category}', got '{actual_category}'"