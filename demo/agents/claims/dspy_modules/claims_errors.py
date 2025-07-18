from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    """Categories of errors for better organization and handling."""

    USER_INPUT = "user_input"  # Error caused by invalid user input
    DATA_ACCESS = "data_access"  # Error accessing or retrieving data
    SYSTEM = "system"  # System or infrastructure error
    MODEL = "model"  # Error from the language model
    SECURITY = "security"  # Security-related error


class ErrorResponse:
    """Standardized error responses for consistent messaging."""

    # User input errors
    INVALID_CLAIM_NUMBER = "Please provide a valid claim number."
    CLAIM_NOT_FOUND = "I couldn't find a claim with that number. Please verify the claim number and try again."
    INVALID_POLICY_NUMBER = "Please provide a valid policy number."
    MISSING_CLAIM_DETAILS = "Please provide details about the incident."
    MISSING_FIELD_NAME = "Please specify which field you want to update."
    MISSING_FIELD_VALUE = "Please provide a value to update the field with."
    FIELD_NOT_FOUND = "That field doesn't exist in our claims records. Available fields include contact information, incident details, and claim status."
    INVALID_FIELD_VALUE = "The value provided isn't valid for this field. Please try again with a proper format."

    # System errors
    GENERIC_ERROR = "I apologize, but I'm experiencing a technical issue. Please try again in a moment."
    DATA_ERROR = "I'm having trouble accessing the claims database right now. Please try again shortly."
    MODEL_ERROR = "I'm having difficulty processing your request right now. Please try again or rephrase your question."

    # Security errors
    SECURITY_FIELD_BLOCKED = "For security reasons, that field cannot be updated. Please contact customer service for assistance."
    SECURITY_INPUT_BLOCKED = "For security reasons, I cannot process that information. Please avoid including sensitive data like credit card numbers or social security numbers."


def get_user_friendly_error(
    error: Exception,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    fallback_message: Optional[str] = None,
) -> str:
    """Convert exceptions to user-friendly error messages based on category."""
    error_str = str(error).lower()

    # Use fallback message if provided
    if fallback_message:
        return fallback_message

    # Map common error patterns to friendly messages
    if category == ErrorCategory.USER_INPUT:
        if "claim" in error_str and "not found" in error_str:
            return ErrorResponse.CLAIM_NOT_FOUND
        elif "invalid" in error_str and "claim" in error_str:
            return ErrorResponse.INVALID_CLAIM_NUMBER
        elif "invalid" in error_str and "policy" in error_str:
            return ErrorResponse.INVALID_POLICY_NUMBER
        elif "field" in error_str and "cannot" in error_str:
            return ErrorResponse.SECURITY_FIELD_BLOCKED
        else:
            return f"There was an issue with your input: {error}"

    elif category == ErrorCategory.SECURITY:
        return ErrorResponse.SECURITY_FIELD_BLOCKED

    elif category == ErrorCategory.MODEL:
        return ErrorResponse.MODEL_ERROR

    elif category == ErrorCategory.DATA_ACCESS:
        return ErrorResponse.DATA_ERROR

    # Default system error
    return ErrorResponse.GENERIC_ERROR
