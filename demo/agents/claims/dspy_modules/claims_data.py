import json
from typing import Optional, Tuple

from agents.claims.types import ClaimRecord

# Logging and tracing setup
from libraries.observability.logger import get_console_logger
from libraries.observability.tracing import create_tracer
from libraries.observability.tracing.otel import safe_set_attribute

from .claims_errors import ErrorCategory, ErrorResponse, get_user_friendly_error
from .claims_validators import ALLOWED_FIELDS, FIELD_VALIDATORS, FieldValidators

logger = get_console_logger("claims_agent.data")
tracer = create_tracer("claims_agent_data")

# Sample in-memory claims database
CLAIMS_DATABASE = [
    ClaimRecord(
        claim_number="1001",
        policy_number="A12345",
        status="In Review",
        estimate=2300.0,
        estimate_date="2026-05-15",
        next_steps="Submit repair estimates",
        outstanding_items=["Repair estimates"],
    ),
    ClaimRecord(
        claim_number="1002",
        policy_number="B67890",
        status="Approved",
        estimate=1500.0,
        estimate_date="2026-04-20",
        next_steps="Processing payment",
        outstanding_items=[],
    ),
    ClaimRecord(
        claim_number="1003",
        policy_number="C24680",
        status="Pending Documentation",
        estimate=None,
        estimate_date=None,
        next_steps="Upload photos and police report",
        outstanding_items=["Photos", "Police report"],
    ),
]


class ClaimDataException(Exception):
    """Custom exception for claim data operations."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.SYSTEM):
        self.message = message
        self.category = category
        super().__init__(message)


def get_claim_record(claim_number: str) -> Optional[ClaimRecord]:
    """Find a claim record by claim number."""
    with tracer.start_as_current_span("get_claim_record") as span:
        safe_set_attribute(span, "claim_number", claim_number)

        clean_claim_number = claim_number.strip() if claim_number else ""

        if not clean_claim_number:
            safe_set_attribute(span, "empty_claim_number", True)
            return None

        for record in CLAIMS_DATABASE:
            if record.claim_number == clean_claim_number:
                safe_set_attribute(span, "claim_found", True)
                return record

        safe_set_attribute(span, "claim_found", False)
        return None


def format_error_response(error_message: str) -> str:
    """Create standardized JSON error response."""
    return json.dumps({"error": error_message})


@tracer.start_as_current_span("get_claim_status")
def get_claim_status(claim_number: str) -> str:
    """Retrieve claim status and details for a given claim_number."""
    try:
        # Validate claim number
        if not claim_number or claim_number.lower() == "unknown":
            logger.warning("Invalid or missing claim number")
            raise ClaimDataException(
                "Invalid claim number provided", ErrorCategory.USER_INPUT
            )

        logger.info(f"Retrieving claim status for claim number: {claim_number}")
        record = get_claim_record(claim_number)

        if not record:
            logger.warning(f"Claim not found: {claim_number}")
            raise ClaimDataException(
                f"Claim {claim_number} not found", ErrorCategory.USER_INPUT
            )

        logger.info(f"Found claim record {claim_number}")
        return record.to_json()

    except ClaimDataException as e:
        return format_error_response(get_user_friendly_error(e, e.category))
    except Exception as e:
        logger.error(f"Unexpected error in get_claim_status: {e}")
        return format_error_response(ErrorResponse.GENERIC_ERROR)


@tracer.start_as_current_span("file_claim")
def file_claim(policy_number: str, claim_details: str) -> str:
    """File a new claim under the given policy with provided details."""
    try:
        # Validate policy number
        if not policy_number or policy_number.lower() == "unknown":
            logger.warning("Invalid or missing policy number")
            raise ClaimDataException(
                "Invalid policy number provided", ErrorCategory.USER_INPUT
            )

        if not claim_details:
            logger.warning("Missing claim details")
            raise ClaimDataException("Missing claim details", ErrorCategory.USER_INPUT)

        logger.info(f"Filing new claim for policy: {policy_number}")

        # Create new claim
        try:
            claim_numbers = [int(r.claim_number) for r in CLAIMS_DATABASE]
            new_number = str(max(claim_numbers) + 1 if claim_numbers else 1001)

            new_claim = ClaimRecord(
                claim_number=new_number,
                policy_number=policy_number.strip(),
                status="Filed",
                next_steps="Provide documentation",
                outstanding_items=["Photos", "Police report"],
                details=claim_details,
            )

            CLAIMS_DATABASE.append(new_claim)
            logger.info(f"New claim filed: {new_number}")
            return new_claim.to_json()
        except ValueError as ve:
            # Handle Pydantic validation errors
            logger.error(f"Validation error creating claim: {ve}")
            raise ClaimDataException(
                f"Invalid claim data: {ve}", ErrorCategory.USER_INPUT
            )

    except ClaimDataException as e:
        return format_error_response(get_user_friendly_error(e, e.category))
    except Exception as e:
        logger.error(f"Error filing claim: {e}")
        return format_error_response(ErrorResponse.GENERIC_ERROR)




@tracer.start_as_current_span("update_field_value")
def update_field_value(
    record: ClaimRecord, field: str, new_value: str
) -> Tuple[bool, Optional[str]]:
    """Update a field in a claim record with validation and type conversion."""
    # Security check - only allow specific fields
    if field not in ALLOWED_FIELDS:
        return False, ErrorResponse.SECURITY_FIELD_BLOCKED

    # Get appropriate validator
    validator = FIELD_VALIDATORS.get(field, FieldValidators.validate_text)

    # Validate and convert value
    success, result = validator(new_value)
    if not success:
        return False, result

    # Update record field with validated value
    try:
        # Create update dict with the single field to update
        update_data = {field: result}

        # Use model_copy to create a new instance with the updated field
        updated_record = record.model_copy(update=update_data)

        # Copy updated values back to original record
        # This approach is needed because we're modifying a shared database record
        for key, value in updated_record.model_dump().items():
            setattr(record, key, value)

        return True, None
    except Exception as e:
        logger.error(f"Error updating field: {e}")
        return False, f"Unable to update field: {str(e)}"


@tracer.start_as_current_span("update_claim_info")
def update_claim_info(claim_number: str, field: str, new_value: str) -> str:
    """Update a given field in the claim record for the specified claim number."""
    try:
        # Validate parameters
        if not claim_number or claim_number.lower() == "unknown":
            logger.warning("Invalid or missing claim number")
            raise ClaimDataException(
                "Invalid claim number provided", ErrorCategory.USER_INPUT
            )

        if not field:
            logger.warning("Missing field name")
            raise ClaimDataException(
                "Missing field to update", ErrorCategory.USER_INPUT
            )

        if new_value is None:
            logger.warning("Missing new value")
            raise ClaimDataException(
                "Missing value for update", ErrorCategory.USER_INPUT
            )

        # Check if field is allowed BEFORE checking if claim exists
        if field not in ALLOWED_FIELDS:
            logger.warning(f"Security: Attempted to update disallowed field '{field}'")
            raise ClaimDataException(
                ErrorResponse.SECURITY_FIELD_BLOCKED, ErrorCategory.SECURITY
            )

        logger.info(f"Updating claim {claim_number}: {field} -> {new_value}")
        record = get_claim_record(claim_number)

        if not record:
            logger.warning(f"Cannot update claim {claim_number}: not found")
            raise ClaimDataException(
                f"Claim {claim_number} not found", ErrorCategory.USER_INPUT
            )

        if not hasattr(record, field):
            logger.warning(f"Field '{field}' not in claim record")
            raise ClaimDataException(
                f"Field '{field}' not in claim record", ErrorCategory.USER_INPUT
            )

        success, error = update_field_value(record, field, new_value)
        if not success:
            logger.error(f"Error updating field: {error}")
            raise ClaimDataException(
                error,
                ErrorCategory.USER_INPUT
                if "invalid" in str(error).lower()
                else ErrorCategory.SECURITY,
            )

        logger.info(f"Successfully updated {field} for claim {claim_number}")
        return record.to_json()

    except ClaimDataException as e:
        return format_error_response(get_user_friendly_error(e, e.category))
    except Exception as e:
        logger.error(f"Unexpected error in update_claim_info: {e}")
        return format_error_response(ErrorResponse.GENERIC_ERROR)
