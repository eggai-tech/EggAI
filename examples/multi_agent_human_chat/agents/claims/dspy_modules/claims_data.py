"""Claims data store and tools for claim operations."""

import json
import re
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator

from libraries.logger import get_console_logger
from libraries.tracing import create_tracer
from libraries.tracing.otel import safe_set_attribute

from .claims_errors import ErrorCategory, ErrorResponse, get_user_friendly_error

logger = get_console_logger("claims_agent.data")
tracer = create_tracer("claims_agent_data")


class ClaimRecord(BaseModel):
    """Data structure for an insurance claim record with validation."""

    claim_number: str = Field(..., description="Unique identifier for the claim")
    policy_number: str = Field(
        ..., description="Policy number associated with the claim"
    )
    status: str = Field(..., description="Current status of the claim")
    next_steps: str = Field(..., description="Next steps required for claim processing")
    outstanding_items: List[str] = Field(
        default_factory=list, description="Items pending for claim processing"
    )
    estimate: Optional[float] = Field(None, description="Estimated payout amount", gt=0)
    estimate_date: Optional[str] = Field(
        None, description="Estimated date for payout (YYYY-MM-DD)"
    )
    details: Optional[str] = Field(
        None, description="Detailed description of the claim"
    )
    address: Optional[str] = Field(None, description="Address related to the claim")
    phone: Optional[str] = Field(None, description="Contact phone number")
    damage_description: Optional[str] = Field(
        None, description="Description of damage or loss"
    )
    contact_email: Optional[str] = Field(None, description="Contact email address")

    @field_validator("estimate_date")
    @classmethod
    def validate_date_format(cls, v):
        """Validate date is in YYYY-MM-DD format."""
        if v is None:
            return v
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is None:
            return v
        # Simple validation - could be enhanced with country-specific patterns
        if not re.match(r"^\+?[\d\-\(\) ]{7,}$", v):
            raise ValueError("Invalid phone number format")
        return v

    def to_dict(self) -> Dict:
        """Convert claim record to dictionary, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def to_json(self) -> str:
        """Convert claim record to JSON string."""
        return json.dumps(self.to_dict())


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


# Field validators registry
class FieldValidators:
    """Validation functions for claim fields."""

    @staticmethod
    def validate_estimate(value: str) -> Tuple[bool, Optional[Union[str, float]]]:
        """Validate estimate field value."""
        try:
            amount = float(value)
            if amount < 0:
                return False, "Estimate cannot be negative"
            return True, amount
        except ValueError:
            return False, "Estimate must be a valid number"

    @staticmethod
    def validate_date(value: str) -> Tuple[bool, Optional[str]]:
        """Validate date field value."""
        if not (value.count("-") == 2 and len(value) >= 8):
            return False, "Date must be in YYYY-MM-DD format"
        try:
            # Basic validation that could be expanded
            year, month, day = value.split("-")
            if not (
                1900 <= int(year) <= 2100
                and 1 <= int(month) <= 12
                and 1 <= int(day) <= 31
            ):
                return False, "Date values out of range"
            return True, value
        except ValueError:
            return False, "Invalid date format, use YYYY-MM-DD"

    @staticmethod
    def validate_items_list(value: str) -> Tuple[bool, Optional[List[str]]]:
        """Validate a comma-separated list of items."""
        if not value or not value.strip():
            return False, "Please provide at least one item"
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            return False, "Please provide at least one item"
        return True, items

    @staticmethod
    def validate_text(value: str) -> Tuple[bool, Optional[str]]:
        """Validate and sanitize text fields."""
        clean_value = value.strip()
        if not clean_value:
            return False, "Value cannot be empty"
        if len(clean_value) > 1000:  # Set reasonable limit
            return False, "Value is too long (max 1000 characters)"
        return True, clean_value


# Field validation registry
FIELD_VALIDATORS = {
    "estimate": FieldValidators.validate_estimate,
    "estimate_date": FieldValidators.validate_date,
    "outstanding_items": FieldValidators.validate_items_list,
    "policy_number": FieldValidators.validate_text,
    "status": FieldValidators.validate_text,
    "details": FieldValidators.validate_text,
    "address": FieldValidators.validate_text,
    "phone": FieldValidators.validate_text,
    "damage_description": FieldValidators.validate_text,
    "contact_email": FieldValidators.validate_text,
    "next_steps": FieldValidators.validate_text,
}

# Explicitly allowed fields to update
ALLOWED_FIELDS = list(FIELD_VALIDATORS.keys())


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
