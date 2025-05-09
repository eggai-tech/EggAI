"""
Shared claims data and tools to prevent circular imports.

This module contains the shared database and tools used by both the main agent
and the optimized DSPy version, preventing circular dependencies.
"""
import json
from libraries.logger import get_console_logger
from libraries.tracing import create_tracer

logger = get_console_logger("claims_agent.data")
tracer = create_tracer("claims_agent_data")

# Sample in-memory claims database
CLAIMS_DATABASE = [
    {
        "claim_number": "1001",
        "policy_number": "A12345",
        "status": "In Review",
        "estimate": 2300.0,
        "estimate_date": "2025-05-15",
        "next_steps": "Submit repair estimates",
        "outstanding_items": ["Repair estimates"]
    },
    {
        "claim_number": "1002",
        "policy_number": "B67890",
        "status": "Approved",
        "estimate": 1500.0,
        "estimate_date": "2025-04-20",
        "next_steps": "Processing payment",
        "outstanding_items": []
    },
    {
        "claim_number": "1003",
        "policy_number": "C24680",
        "status": "Pending Documentation",
        "estimate": None,
        "estimate_date": None,
        "next_steps": "Upload photos and police report",
        "outstanding_items": ["Photos", "Police report"]
    },
]


@tracer.start_as_current_span("get_claim_status")
def get_claim_status(claim_number: str) -> str:
    """
    Retrieve claim status and details for a given claim_number.

    Args:
        claim_number (str): The unique identifier of the claim to retrieve.

    Returns:
        str: JSON string containing claim data or an error message.
    """
    logger.info(f"Retrieving claim status for claim number: {claim_number}")
    for record in CLAIMS_DATABASE:
        if record["claim_number"] == claim_number.strip():
            logger.info(f"Found claim record {claim_number}")
            return json.dumps(record)
    logger.warning(f"Claim not found: {claim_number}")
    return json.dumps({"error": "Claim not found."})


@tracer.start_as_current_span("file_claim")
def file_claim(policy_number: str, claim_details: str) -> str:
    """
    File a new claim under the given policy with provided details.

    Args:
        policy_number (str): The policy number under which to file the claim.
        claim_details (str): Description of the incident or damage.

    Returns:
        str: JSON string of the newly created claim record.
    """
    logger.info(f"Filing new claim for policy: {policy_number}")
    existing = [int(r["claim_number"]) for r in CLAIMS_DATABASE]
    new_number = str(max(existing) + 1 if existing else 1001)
    new_claim = {
        "claim_number": new_number,
        "policy_number": policy_number.strip(),
        "status": "Filed",
        "estimate": None,
        "estimate_date": None,
        "next_steps": "Provide documentation",
        "outstanding_items": ["Photos", "Police report"],
        "details": claim_details
    }
    CLAIMS_DATABASE.append(new_claim)
    logger.info(f"New claim filed: {new_number}")
    return json.dumps(new_claim)


@tracer.start_as_current_span("update_claim_info")
def update_claim_info(claim_number: str, field: str, new_value: str) -> str:
    """
    Update a given field in the claim record for the specified claim_number.

    Args:
        claim_number (str): The unique identifier of the claim to update.
        field (str): The field name to modify in the claim record.
        new_value (str): The new value to set for the specified field.

    Returns:
        str: JSON string of the updated claim record or an error message.
    """
    logger.info(f"Updating claim {claim_number}: {field} -> {new_value}")
    for record in CLAIMS_DATABASE:
        if record["claim_number"] == claim_number.strip():
            if field in record:
                try:
                    if field == "estimate":
                        record[field] = float(new_value)
                    elif field == "outstanding_items":
                        record[field] = [item.strip() for item in new_value.split(",")]
                    else:
                        record[field] = new_value
                except ValueError:
                    error_msg = f"Invalid value for {field}: {new_value}"
                    logger.error(error_msg)
                    return json.dumps({"error": error_msg})
                logger.info(f"Successfully updated {field} for claim {claim_number}")
                return json.dumps(record)
            logger.warning(f"Field '{field}' not in claim record.")
            return json.dumps({"error": f"Field '{field}' not in claim record."})

    logger.warning(f"Cannot update claim {claim_number}: not found")
    return json.dumps({"error": "Claim not found."})