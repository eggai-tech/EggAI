"""Tests for claims DSPy module to improve coverage."""

import pytest

from agents.claims.dspy_modules.claims import (
    ClaimsSignature,
    ModelConfig,
    claims_optimized_dspy,
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


def test_claims_signature():
    """Test ClaimsSignature structure."""
    shared_signature_structure(ClaimsSignature)


def test_claims_signature_fields():
    """Test that ClaimsSignature has expected fields."""
    shared_signature_fields(ClaimsSignature)


@pytest.mark.asyncio
async def test_claims_optimized_dspy_basic():
    """Test basic functionality of claims_optimized_dspy."""
    conversation = "User: I need to file a claim for my car accident\nClaimsAgent: I can help with that."
    expected_response = "I'll help you file your claim. Please provide your policy number and details about the incident."
    await shared_dspy_basic(claims_optimized_dspy, conversation, expected_response)


@pytest.mark.asyncio
async def test_claims_optimized_dspy_empty_conversation():
    """Test claims_optimized_dspy with empty conversation."""
    expected_response = "I need more information about your claim to help you."
    await shared_dspy_empty(claims_optimized_dspy, expected_response)


def test_model_config_validation():
    """Test ModelConfig validation."""
    shared_model_config(ModelConfig)


def test_truncate_long_history_with_config():
    """Test truncate_long_history with custom config."""
    shared_truncate_config(truncate_long_history, ModelConfig, "claim")


def test_truncate_long_history_return_structure():
    """Test the return structure of truncate_long_history."""
    shared_truncate_structure(truncate_long_history)
