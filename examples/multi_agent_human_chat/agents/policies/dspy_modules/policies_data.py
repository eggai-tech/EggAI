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


@tracer.start_as_current_span("query_policy_documentation")
def query_policy_documentation(query: str, policy_category: PolicyCategory) -> str:
    """
    Retrieves policy documentation based on a query and policy category using Temporal workflow.
    Returns a JSON-formatted string with the documentation results.
    """
    logger.info(
        f"Tool called: query_policy_documentation(query='{query[:50]}...', policy_category='{policy_category}')"
    )
    try:
        # Try to use Temporal workflow for documentation queries
        try:
            import asyncio

            from agents.policies.rag.documentation_temporal_client import (
                DocumentationTemporalClient,
            )

            logger.info(
                f"Using Temporal workflow for documentation query: '{query}', category: '{policy_category}'"
            )

            async def run_temporal_query():
                client = DocumentationTemporalClient()
                result = await client.query_documentation_async(query, policy_category)
                await client.close()
                return result

            # Run the async function in a thread
            def temporal_query():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(run_temporal_query())
                finally:
                    loop.close()

            thread = ThreadWithResult(target=temporal_query)
            thread.start()
            result = thread.join()

            if result and result.success:
                logger.info(
                    f"Temporal documentation query successful: {len(result.results)} results"
                )
                if len(result.results) >= 2:
                    return json.dumps([result.results[0], result.results[1]])
                return json.dumps(result.results)
            else:
                logger.warning(
                    f"Temporal documentation query failed: {result.error_message if result else 'No result'}"
                )
                raise Exception("Temporal query failed")

        except Exception as temporal_error:
            logger.warning(
                f"Temporal workflow unavailable for documentation query: {temporal_error}"
            )
            # Fallback to direct retrieval only for documentation queries
            logger.info("Falling back to direct retrieval for documentation")
            from agents.policies.rag.retrieving import retrieve_policies

            thread = ThreadWithResult(
                target=retrieve_policies, args=(query, policy_category)
            )
            thread.start()
            results = thread.join()

            if results:
                logger.info(f"Found documentation via fallback: {len(results)} results")
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
                # Format monetary values with proper currency notation
                if policy.get("premium_amount"):
                    policy["premium_amount_usd"] = f"${policy['premium_amount']:.2f}"

                # Ensure critical fields are explicitly labeled for importance
                if "due_date" in policy:
                    policy["payment_due_date"] = policy["due_date"]
                    policy["next_payment_date"] = policy["due_date"]
                return json.dumps(policy)

        logger.warning(f"Policy not found: '{policy_number}'")
        return "Policy not found."
    except Exception as e:
        logger.error(f"Error retrieving policy by number: {e}", exc_info=True)
        return f"Error retrieving policy: {str(e)}"
