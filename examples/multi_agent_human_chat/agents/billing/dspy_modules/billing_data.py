"""Billing data access module."""
import json

from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.data")

BILLING_DATABASE = [
    {
        "policy_number": "A12345",
        "billing_cycle": "Monthly",
        "amount_due": 120.0,
        "due_date": "2026-02-01",
        "status": "Paid",
    },
    {
        "policy_number": "B67890",
        "billing_cycle": "Quarterly",
        "amount_due": 300.0,
        "due_date": "2026-03-15",
        "status": "Pending",
    },
    {
        "policy_number": "C24680",
        "billing_cycle": "Annual",
        "amount_due": 1000.0,
        "due_date": "2026-12-01",
        "status": "Pending",
    },
]


def get_policy_record(policy_number: str):
    """Get a policy record by policy number."""
    clean_policy_number = policy_number.strip()
    for record in BILLING_DATABASE:
        if record["policy_number"] == clean_policy_number:
            return record
    return None


def get_billing_info(policy_number: str):
    """Retrieve billing information for a policy number."""
    logger.info(f"Retrieving billing info for policy number: {policy_number}")
    record = get_policy_record(policy_number)
    
    if record:
        logger.info(f"Found billing record for policy {policy_number}")
        return json.dumps(record)
    
    logger.warning(f"Policy not found: {policy_number}")
    return json.dumps({"error": "Policy not found."})


def update_billing_info(policy_number: str, field: str, new_value: str):
    """Update billing information for a policy record."""
    logger.info(f"Updating billing info for policy {policy_number}: {field} -> {new_value}")
    record = get_policy_record(policy_number)
    
    if not record:
        logger.warning(f"Cannot update policy {policy_number}: not found")
        return json.dumps({"error": "Policy not found."})
        
    if field not in record:
        error_msg = f"Field '{field}' not found in billing record."
        logger.warning(error_msg)
        return json.dumps({"error": error_msg})
        
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