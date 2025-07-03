"""Tests for billing DSPy module to improve coverage."""

import pytest

from libraries.billing_dspy.billing import (
    BillingSignature,
    ModelConfig,
    billing_optimized_dspy,
    truncate_long_history,
)
from agents.shared_test_utils import (
    test_model_config_validation as shared_model_config,
)
from agents.shared_test_utils import (
    test_optimized_dspy_basic as shared_dspy_basic,
)
from agents.shared_test_utils import (
    test_optimized_dspy_empty_conversation as shared_dspy_empty,
)
from agents.shared_test_utils import (
    test_signature_fields as shared_signature_fields,
)
from agents.shared_test_utils import (
    test_signature_structure as shared_signature_structure,
)
from agents.shared_test_utils import (
    test_truncate_long_history_edge_cases as shared_truncate_edge_cases,
)
from agents.shared_test_utils import (
    test_truncate_long_history_return_structure as shared_truncate_structure,
)
from agents.shared_test_utils import (
    test_truncate_long_history_with_config as shared_truncate_config,
)


def test_truncate_long_history_edge_cases():
    """Test edge cases for truncate_long_history function."""
    shared_truncate_edge_cases(truncate_long_history, ModelConfig)


def test_billing_signature():
    """Test BillingSignature structure."""
    shared_signature_structure(BillingSignature)


def test_billing_signature_fields():
    """Test that BillingSignature has expected fields."""
    shared_signature_fields(BillingSignature)


@pytest.mark.asyncio
async def test_billing_optimized_dspy_basic():
    """Test basic functionality of billing_optimized_dspy."""
    conversation = (
        "User: What's my current bill?\nBillingAgent: Let me check that for you."
    )
    expected_response = (
        "Your current balance is $125.50. Your next payment is due on March 15th."
    )
    await shared_dspy_basic(billing_optimized_dspy, conversation, expected_response)


@pytest.mark.asyncio
async def test_billing_optimized_dspy_empty_conversation():
    """Test billing_optimized_dspy with empty conversation."""
    expected_response = "I need more information about your account to help you."
    await shared_dspy_empty(billing_optimized_dspy, expected_response)


def test_model_config_validation():
    """Test ModelConfig validation."""
    shared_model_config(ModelConfig)


def test_truncate_long_history_with_config():
    """Test truncate_long_history with custom config."""
    shared_truncate_config(truncate_long_history, ModelConfig, "billing")


def test_truncate_long_history_return_structure():
    """Test the return structure of truncate_long_history."""
    shared_truncate_structure(truncate_long_history)
