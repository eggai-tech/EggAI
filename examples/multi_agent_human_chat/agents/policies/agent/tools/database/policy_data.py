"""Policy database access tool.

NOTE: This module currently uses example data for demonstration purposes.
In production, the get_personal_policy_details function should be updated
to query a real database (e.g., PostgreSQL, MongoDB, etc.).

The USE_EXAMPLE_DATA flag in example_data.py controls whether to use
the example policies or attempt a real database query.
"""

import json

from opentelemetry import trace

from agents.policies.agent.tools.database.example_data import (
    EXAMPLE_POLICIES,
    USE_EXAMPLE_DATA,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.tools.database")
tracer = trace.get_tracer("policies_agent_tools_database")


@tracer.start_as_current_span("get_personal_policy_details")
def get_personal_policy_details(policy_number: str) -> str:
    """
    Retrieve specific policy details from database using policy number.
    Use this when user provides a policy number and wants their personal policy information.
    Returns JSON with policy data or error message.

    Args:
        policy_number: The policy number to look up

    Returns:
        JSON string with policy details or error message
    """
    logger.info(f"Retrieving policy details for policy number: '{policy_number}'")

    if not policy_number:
        return "Policy not found."

    try:
        cleaned_policy_number = policy_number.strip().upper()
        
        # In production, this would query a real database
        # For now, use example data if enabled
        if USE_EXAMPLE_DATA:
            policies_to_search = EXAMPLE_POLICIES
        else:
            # TODO: Replace with actual database query
            logger.warning("Production database not configured, using empty dataset")
            policies_to_search = []
        
        for policy in policies_to_search:
            if policy["policy_number"] == cleaned_policy_number:
                logger.info(
                    f"Found policy: {policy['policy_number']} for {policy['name']}"
                )
                policy_copy = policy.copy()
                if policy_copy.get("premium_amount"):
                    policy_copy["premium_amount_usd"] = (
                        f"${policy_copy['premium_amount']:.2f}"
                    )
                return json.dumps(policy_copy)

        logger.warning(f"Policy not found: '{policy_number}'")
        return "Policy not found."
    except Exception as e:
        logger.error(f"Error retrieving policy: {e}", exc_info=True)
        return "Policy not found."
