"""
This module contains the shared database and tools used by both the main agent
and the optimized DSPy version, preventing circular dependencies.
"""
import json
from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.data")

# Billing database with consistent YYYY-MM-DD dates
BILLING_DATABASE = [
    {
        "policy_number": "A12345",
        "billing_cycle": "Monthly",
        "amount_due": 120.0,
        "due_date": "2025-02-01",
        "status": "Paid",
    },
    {
        "policy_number": "B67890",
        "billing_cycle": "Quarterly",
        "amount_due": 300.0,
        "due_date": "2025-03-15",
        "status": "Pending",
    },
    {
        "policy_number": "C24680",
        "billing_cycle": "Annual",
        "amount_due": 1000.0,
        "due_date": "2025-12-01",
        "status": "Pending",
    },
]


def get_billing_info(policy_number: str):
    """
    Retrieve billing information for a given policy_number.
    Return a JSON object with billing fields if found, or {"error": "Policy not found."} if missing.
    """
    logger.info(f"Retrieving billing info for policy number: {policy_number}")
    for record in BILLING_DATABASE:
        if record["policy_number"] == policy_number.strip():
            logger.info(f"Found billing record for policy {policy_number}")
            return json.dumps(record)
    logger.warning(f"Policy not found: {policy_number}")
    return json.dumps({"error": "Policy not found."})


def update_billing_info(policy_number: str, field: str, new_value: str):
    """
    Update a given field in the billing record for the specified policy_number.
    Return the updated record as JSON if successful, or an error message if policy not found.
    """
    logger.info(f"Updating billing info for policy {policy_number}: {field} -> {new_value}")

    for record in BILLING_DATABASE:
        if record["policy_number"] == policy_number.strip():
            if field in record:
                if field == "amount_due":
                    try:
                        record[field] = float(new_value)
                    except ValueError:
                        error_msg = f"Invalid numeric value for {field}: {new_value}"
                        logger.error(error_msg)
                        return json.dumps({"error": error_msg})
                else:
                    record[field] = new_value
                logger.info(f"Successfully updated {field} for policy {policy_number}")
                return json.dumps(record)
            else:
                error_msg = f"Field '{field}' not found in billing record."
                logger.warning(error_msg)
                return json.dumps({"error": error_msg})

    logger.warning(f"Cannot update policy {policy_number}: not found")
    return json.dumps({"error": "Policy not found."})