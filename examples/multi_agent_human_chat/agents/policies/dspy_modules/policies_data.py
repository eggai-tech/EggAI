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

# Sample in-memory policies database
POLICIES_DATABASE = [
    {
        "policy_number": "A12345",
        "name": "John Doe",
        "policy_category": "auto",
        "premium_amount": 500,
        "due_date": "2025-03-01",
    },
    {
        "policy_number": "B67890",
        "name": "Jane Smith",
        "policy_category": "life",
        "premium_amount": 300,
        "due_date": "2025-03-15",
    },
    {
        "policy_number": "C24680",
        "name": "Alice Johnson",
        "policy_category": "home",
        "premium_amount": 400,
        "due_date": "2025-03-01",
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


@tracer.start_as_current_span("query_policy_documentation")
def query_policy_documentation(query: str, policy_category: PolicyCategory) -> str:
    """
    Retrieves policy documentation based on a query and policy category.
    Returns a JSON-formatted string with the documentation results.
    """
    try:
        from agents.policies.rag.retrieving import retrieve_policies
        
        logger.info(
            f"Retrieving policy information for query: '{query}', category: '{policy_category}'"
        )
        thread = ThreadWithResult(
            target=retrieve_policies, args=(query, policy_category)
        )
        thread.start()
        results = thread.join()

        if results:
            logger.info(f"Found documentation: {len(results)} results")
            if len(results) >= 2:
                return json.dumps([results[0], results[1]])
            return json.dumps(results)

        logger.warning(
            f"No documentation found for query: '{query}', category: '{policy_category}'"
        )
        return "Documentation not found."
    except Exception as e:
        logger.error(f"Error retrieving policy documentation: {e}", exc_info=True)
        return "Error retrieving documentation."


@tracer.start_as_current_span("take_policy_by_number_from_database")
def take_policy_by_number_from_database(policy_number: str) -> str:
    """
    Retrieves detailed information for a given policy number.
    Returns a JSON-formatted string if the policy is found, or "Policy not found." otherwise.
    """
    logger.info(f"Retrieving policy details for policy number: '{policy_number}'")

    if not policy_number:
        logger.warning("Empty policy number provided")
        return "Invalid policy number format."

    try:
        cleaned_policy_number = policy_number.strip()
        for policy in POLICIES_DATABASE:
            if policy["policy_number"] == cleaned_policy_number:
                logger.info(
                    f"Found policy: {policy['policy_number']} for {policy['name']}"
                )
                return json.dumps(policy)

        logger.warning(f"Policy not found: '{policy_number}'")
        return "Policy not found."
    except Exception as e:
        logger.error(f"Error retrieving policy by number: {e}", exc_info=True)
        return f"Error retrieving policy: {str(e)}"