"""Tests for policy data module"""
import json

from agents.policies.agent.tools.database.example_data import EXAMPLE_POLICIES
from agents.policies.agent.tools.database.policy_data import (
    get_all_policies,
    get_personal_policy_details,
)


def test_get_all_policies():
    """Test getting all policies"""
    policies = get_all_policies()
    assert isinstance(policies, list)
    assert len(policies) == len(EXAMPLE_POLICIES)
    
    # Check structure of first policy
    if policies:
        first_policy = policies[0]
        assert "policy_number" in first_policy
        assert "name" in first_policy
        assert "policy_category" in first_policy
        assert "status" in first_policy


def test_get_personal_policy_details_exists():
    """Test getting details for existing policy"""
    # Test with a known policy
    result = get_personal_policy_details("A12345")
    assert result != "Policy not found."
    
    # Parse the JSON result
    policy_data = json.loads(result)
    assert policy_data["policy_number"] == "A12345"
    assert "name" in policy_data
    assert "premium_amount" in policy_data


def test_get_personal_policy_details_not_found():
    """Test getting details for non-existent policy"""
    result = get_personal_policy_details("INVALID123")
    assert result == "Policy not found."


def test_get_personal_policy_details_empty():
    """Test getting details with empty policy number"""
    result = get_personal_policy_details("")
    assert result == "Policy not found."


def test_get_personal_policy_details_strips_whitespace():
    """Test that policy number whitespace is handled"""
    # Add spaces around valid policy number
    result = get_personal_policy_details("  A12345  ")
    assert result != "Policy not found."
    
    policy_data = json.loads(result)
    assert policy_data["policy_number"] == "A12345"