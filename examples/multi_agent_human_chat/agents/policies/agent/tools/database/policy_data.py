"""Policy database access tool."""

import json
from typing import Dict, List

from opentelemetry import trace

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.tools.database")
tracer = trace.get_tracer("policies_agent_tools_database")


# Sample in-memory policies database
POLICIES_DATABASE: List[Dict] = [
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
        cleaned_policy_number = policy_number.strip()
        for policy in POLICIES_DATABASE:
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
