"""
Shared policies data and tools to prevent circular imports.

This module contains the shared database and tools used by both the main agent
and the optimized DSPy version, preventing circular dependencies.
"""

import asyncio
import json
import threading
import uuid
from typing import Literal

from eggai import Channel
from opentelemetry import trace

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage

PolicyCategory = Literal["auto", "life", "home", "health"]

logger = get_console_logger("policies_agent.data")
tracer = trace.get_tracer("policies_agent_data")

# Sample in-memory policies database
POLICIES_DATABASE = [
    {
        "policy_number": "A12345",
        "name": "John Doe",
        "policy_category": "home",
        "premium_amount": 500,
        "due_date": "2026-03-01",
    },
    {
        "policy_number": "B67890",
        "name": "Jane Smith",
        "policy_category": "life",
        "premium_amount": 300,
        "due_date": "2026-03-15",
    },
    {
        "policy_number": "C24680",
        "name": "Alice Johnson",
        "policy_category": "auto",
        "premium_amount": 400,
        "due_date": "2026-03-01",
    },
]


def add_test_policy(
    policy_number: str, policy_category: PolicyCategory, name: str = "Test User"
) -> None:
    """
    Add a test policy to the database dynamically.
    Used by test cases to ensure policy exists for testing RAG functionality.
    """
    # Check if policy already exists
    for policy in POLICIES_DATABASE:
        if policy["policy_number"] == policy_number:
            logger.info(f"Policy {policy_number} already exists in database")
            return

    # Create test policy entry
    test_policy = {
        "policy_number": policy_number,
        "name": name,
        "policy_category": policy_category,
        "premium_amount": 300,
        "due_date": "2026-03-15",
    }

    POLICIES_DATABASE.append(test_policy)
    logger.info(f"Added test policy {policy_number} ({policy_category}) to database")


def remove_test_policy(policy_number: str) -> None:
    """
    Remove a test policy from the database.
    Used for cleanup after tests.
    """
    global POLICIES_DATABASE
    POLICIES_DATABASE = [
        p for p in POLICIES_DATABASE if p["policy_number"] != policy_number
    ]
    logger.info(f"Removed test policy {policy_number} from database")


class ThreadWithResult(threading.Thread):
    def __init__(self, target, args=(), kwargs=None):
        super().__init__(target=target, args=args, kwargs=kwargs or {})
        self._result = None

    def run(self):
        if self._target:
            self._result = self._target(*self._args, **self._kwargs)

    def join(self, *args):
        super().join(*args)
        return self._result


# Global variables for knowledge base communication
_pending_knowledge_base_requests = {}
_knowledge_base_responses = {}
agents_channel = Channel(channels.agents)


def _run_async_in_thread(coro):
    """Run async coroutine in a thread with its own event loop."""
    import concurrent.futures
    
    def run_in_thread():
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            if loop:
                loop.close()
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=30.0)  # 30 second timeout


async def _send_knowledge_base_request(query: str, policy_category: PolicyCategory) -> str:
    """Send request to knowledge base agent and wait for response."""
    request_id = str(uuid.uuid4())
    
    try:
        # Create documentation request
        documentation_request = TracedMessage(
            type="documentation_request",
            source="PoliciesAgent",
            data={
                "chat_messages": [
                    {
                        "role": "User",
                        "content": f"I need information about {query} for {policy_category} policy. Please provide specific details from the documentation."
                    }
                ],
                "connection_id": f"policies_tool_{request_id}",
                "streaming": False,
                "request_id": request_id
            }
        )
        
        # Store pending request
        response_future = asyncio.Future()
        _pending_knowledge_base_requests[request_id] = response_future
        
        # Send request
        await agents_channel.publish(documentation_request)
        logger.info(f"Sent knowledge base request with ID: {request_id}")
        
        # Wait for response
        try:
            response = await asyncio.wait_for(response_future, timeout=25.0)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for knowledge base response for request {request_id}")
            return f"Timeout: Unable to retrieve documentation for {query}. Please try again."
        
    except Exception as e:
        logger.error(f"Error communicating with knowledge base: {e}")
        return f"Error retrieving documentation: {str(e)}"
    finally:
        # Clean up
        _pending_knowledge_base_requests.pop(request_id, None)


def handle_knowledge_base_response(msg: TracedMessage) -> None:
    """Handle responses from the knowledge base agent."""
    if msg.type == "documentation_response" and msg.source == "PolicyDocumentationAgent":
        request_id = msg.data.get("request_id", "")
        if request_id and request_id in _pending_knowledge_base_requests:
            future = _pending_knowledge_base_requests[request_id]
            if not future.done():
                response_message = msg.data.get("response", "No documentation found.")
                future.set_result(response_message)
                logger.info(f"Received knowledge base response for request {request_id}")
            else:
                logger.warning(f"Future already done for request {request_id}")
        else:
            logger.warning(f"Request ID {request_id} not found in pending requests. Available: {list(_pending_knowledge_base_requests.keys())}")
    elif msg.type == "agent_message" and msg.source == "PolicyDocumentationAgent":
        # Legacy support for old message format - try both request_id and connection_id parsing
        request_id = msg.data.get("request_id", "")
        if not request_id:
            # Fallback to parsing from connection_id
            connection_id = msg.data.get("connection_id", "")
            if connection_id.startswith("policies_tool_"):
                request_id = connection_id.replace("policies_tool_", "")
        
        if request_id and request_id in _pending_knowledge_base_requests:
            future = _pending_knowledge_base_requests[request_id]
            if not future.done():
                response_message = msg.data.get("message", "No documentation found.")
                future.set_result(response_message)
                logger.info(f"Received knowledge base response for request {request_id}")
            else:
                logger.warning(f"Future already done for request {request_id}")
        else:
            logger.warning(f"Request ID {request_id} not found in pending requests. Available: {list(_pending_knowledge_base_requests.keys())}")


@tracer.start_as_current_span("query_policy_documentation")
def query_policy_documentation(query: str, policy_category: PolicyCategory) -> str:
    """
    Retrieves policy documentation by sending request to knowledge_base_agent.
    This function communicates with the knowledge base agent via async messaging.
    """
    logger.info(
        f"Tool called: query_policy_documentation(query='{query[:50]}...', policy_category='{policy_category}')"
    )
    
    try:
        # Use thread to run async communication
        response = _run_async_in_thread(
            _send_knowledge_base_request(query, policy_category)
        )
        logger.info(f"Received knowledge base response: {response[:100]}...")
        return response
        
    except Exception as e:
        logger.error(f"Error in knowledge base communication: {e}")
        return f"Unable to retrieve documentation for '{query}' at this time. Please try again later."


@tracer.start_as_current_span("take_policy_by_number_from_database")
def take_policy_by_number_from_database(policy_number: str) -> str:
    """
    Retrieves detailed information for a given policy number.
    Returns a JSON-formatted string if the policy is found, or an error message.
    """
    if not policy_number:
        return "Error: Empty policy number provided."

    try:
        cleaned_policy_number = policy_number.strip()
        for policy in POLICIES_DATABASE:
            if policy["policy_number"] == cleaned_policy_number:
                return json.dumps(policy)
        
        return f"Error: Policy {cleaned_policy_number} not found."
    except Exception as e:
        return f"Error: {str(e)}"
