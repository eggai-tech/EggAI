"""Field validators and registry for the Claims Agent."""

from typing import List, Optional, Tuple, Union


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
        if len(clean_value) > 1000:
            return False, "Value is too long (max 1000 characters)"
        return True, clean_value


# Field validation registry mapping field names to validators
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

# Explicitly allowed fields to update (security whitelist)
ALLOWED_FIELDS = list(FIELD_VALIDATORS.keys())