"""
Shared policies data and tools to prevent circular imports.

This module contains the shared database and tools used by both the main agent
and the optimized DSPy version, preventing circular dependencies.
"""

import json
import threading
from typing import Literal

from opentelemetry import trace

from libraries.logger import get_console_logger

PolicyCategory = Literal["auto", "life", "home", "health"]

logger = get_console_logger("policies_agent.data")
tracer = trace.get_tracer("policies_agent_data")

# Tool for direct policy retrieval
@tracer.start_as_current_span("search_policy_documentation")
def search_policy_documentation(query: str, category: str = None) -> str:
    """
    Search policy documentation and coverage information using RAG.
    Use this for general policy questions that don't require personal policy data.
    Returns a JSON-formatted string with the retrieval results.
    """
    logger.info(
        f"Tool called: search_policy_documentation(query='{query[:50]}...', category='{category}')"
    )
    try:
        from agents.policies.retrieving import retrieve_policies

        thread = ThreadWithResult(
            target=retrieve_policies, args=(query, category)
        )
        thread.start()
        results = thread.join()

        if results:
            logger.info(f"Found policy information via direct retrieval: {len(results)} results")
            if len(results) >= 2:
                return json.dumps([results[0], results[1]])
            return json.dumps(results)

        logger.warning(
            f"No policy information found for query: '{query}', category: '{category}'"
        )
        return "Policy information not found."
    except Exception as e:
        logger.error(f"Error retrieving policy information: {e}", exc_info=True)
        return "Error retrieving policy information."


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




@tracer.start_as_current_span("get_personal_policy_details")
def get_personal_policy_details(policy_number: str) -> str:
    """Retrieve specific policy details from database using policy number.
    Use this when user provides a policy number and wants their personal policy information.
    Returns JSON with policy data or error message."""
    logger.info(f"Retrieving policy details for policy number: '{policy_number}'")

    if not policy_number:
        return "Policy not found."

    try:
        cleaned_policy_number = policy_number.strip()
        for policy in POLICIES_DATABASE:
            if policy["policy_number"] == cleaned_policy_number:
                logger.info(f"Found policy: {policy['policy_number']} for {policy['name']}")
                policy_copy = policy.copy()
                if policy_copy.get("premium_amount"):
                    policy_copy["premium_amount_usd"] = f"${policy_copy['premium_amount']:.2f}"
                return json.dumps(policy_copy)

        logger.warning(f"Policy not found: '{policy_number}'")
        return "Policy not found."
    except Exception as e:
        logger.error(f"Error retrieving policy: {e}", exc_info=True)
        return "Policy not found."
