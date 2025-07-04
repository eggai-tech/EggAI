"""Tests for billing data module."""

import json

import pytest

from agents.billing.dspy_modules.billing_data import (
    BILLING_DATABASE,
    get_billing_info,
    get_policy_record,
    update_billing_info,
)


def test_get_policy_record_existing():
    """Test getting an existing policy record."""
    record = get_policy_record("A12345")
    assert record is not None
    assert record["policy_number"] == "A12345"
    assert record["billing_cycle"] == "Monthly"
    assert record["amount_due"] == pytest.approx(120.0)


def test_get_policy_record_nonexistent():
    """Test getting a non-existent policy record."""
    record = get_policy_record("NONEXISTENT")
    assert record is None


def test_get_policy_record_with_whitespace():
    """Test getting a policy record with whitespace."""
    record = get_policy_record("  A12345  ")
    assert record is not None
    assert record["policy_number"] == "A12345"


def test_get_billing_info_existing_policy():
    """Test getting billing info for existing policy."""
    result = get_billing_info("B67890")
    data = json.loads(result)

    assert data["policy_number"] == "B67890"
    assert data["billing_cycle"] == "Quarterly"
    assert data["amount_due"] == pytest.approx(300.0)
    assert data["due_date"] == "2026-03-15"
    assert data["status"] == "Pending"


def test_get_billing_info_nonexistent_policy():
    """Test getting billing info for non-existent policy."""
    result = get_billing_info("NONEXISTENT")
    data = json.loads(result)

    assert "error" in data
    assert data["error"] == "Policy not found."


def test_update_billing_info_valid_field():
    """Test updating a valid field."""
    # First, get the original value
    original_record = get_policy_record("C24680")
    original_status = original_record["status"]

    # Update the status
    result = update_billing_info("C24680", "status", "Paid")
    data = json.loads(result)

    assert data["policy_number"] == "C24680"
    assert data["status"] == "Paid"

    # Verify the change persisted
    updated_record = get_policy_record("C24680")
    assert updated_record["status"] == "Paid"

    # Restore original value for other tests
    update_billing_info("C24680", "status", original_status)


def test_update_billing_info_amount_due():
    """Test updating amount_due field with numeric conversion."""
    # Get original value
    original_record = get_policy_record("A12345")
    original_amount = original_record["amount_due"]

    # Update amount_due
    result = update_billing_info("A12345", "amount_due", "150.50")
    data = json.loads(result)

    assert data["amount_due"] == pytest.approx(150.50)

    # Restore original value
    update_billing_info("A12345", "amount_due", str(original_amount))


def test_update_billing_info_invalid_amount():
    """Test updating amount_due with invalid numeric value."""
    result = update_billing_info("A12345", "amount_due", "invalid_number")
    data = json.loads(result)

    assert "error" in data
    assert "Invalid numeric value" in data["error"]


def test_update_billing_info_nonexistent_policy():
    """Test updating billing info for non-existent policy."""
    result = update_billing_info("NONEXISTENT", "status", "Paid")
    data = json.loads(result)

    assert "error" in data
    assert data["error"] == "Policy not found."


def test_update_billing_info_invalid_field():
    """Test updating a non-existent field."""
    result = update_billing_info("A12345", "invalid_field", "some_value")
    data = json.loads(result)

    assert "error" in data
    assert "Field 'invalid_field' not found" in data["error"]


def test_billing_database_structure():
    """Test that the billing database has expected structure."""
    assert len(BILLING_DATABASE) >= 3

    for record in BILLING_DATABASE:
        assert "policy_number" in record
        assert "billing_cycle" in record
        assert "amount_due" in record
        assert "due_date" in record
        assert "status" in record

        # Verify data types
        assert isinstance(record["policy_number"], str)
        assert isinstance(record["billing_cycle"], str)
        assert isinstance(record["amount_due"], (int, float))
        assert isinstance(record["due_date"], str)
        assert isinstance(record["status"], str)


def test_update_billing_info_string_field():
    """Test updating a string field like billing_cycle."""
    # Get original value
    original_record = get_policy_record("B67890")
    original_cycle = original_record["billing_cycle"]

    # Update billing_cycle
    result = update_billing_info("B67890", "billing_cycle", "Monthly")
    data = json.loads(result)

    assert data["billing_cycle"] == "Monthly"

    # Restore original value
    update_billing_info("B67890", "billing_cycle", original_cycle)


def test_update_billing_info_due_date():
    """Test updating due_date field."""
    # Get original value
    original_record = get_policy_record("C24680")
    original_date = original_record["due_date"]

    # Update due_date
    new_date = "2026-06-01"
    result = update_billing_info("C24680", "due_date", new_date)
    data = json.loads(result)

    assert data["due_date"] == new_date

    # Restore original value
    update_billing_info("C24680", "due_date", original_date)
