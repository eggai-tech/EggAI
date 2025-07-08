"""
DSPy-specific test helpers.

These utilities help with testing DSPy modules and signatures.
"""

from typing import Callable, Type
from unittest.mock import patch

import pytest


def test_truncate_long_history_edge_cases(truncate_func: Callable, model_config_class: Type) -> None:
    """Shared test for truncate_long_history edge cases."""
    result = truncate_func("")
    assert result["history"] == ""
    assert not result["truncated"]

    short_history = "Line 1\nLine 2\nLine 3"
    result = truncate_func(short_history, model_config_class(truncation_length=2000))
    assert result["history"] == short_history
    assert not result["truncated"]

    long_history = "\n".join(
        [
            f"This is a much longer line {i} with more content to make it exceed the truncation length"
            for i in range(100)
        ]
    )
    result = truncate_func(long_history, model_config_class(truncation_length=1000))
    assert result["truncated"]
    assert result["original_length"] > result["truncated_length"]
    lines = result["history"].split("\n")
    assert len(lines) == 30
    assert "line 99" in result["history"]


def test_signature_structure(signature_class: Type, test_data: str = "test") -> None:
    """Shared test for signature structure."""
    signature = signature_class(chat_history=test_data, final_response=test_data)

    assert hasattr(signature, "chat_history")
    assert hasattr(signature, "final_response")

    assert signature.chat_history == test_data
    assert signature.final_response == test_data


def test_signature_fields(signature_class: Type) -> None:
    """Shared test for signature fields."""
    fields = signature_class.fields
    field_names = set(fields.keys())

    assert "chat_history" in field_names
    assert "final_response" in field_names

    conversation_field = fields["chat_history"]
    response_field = fields["final_response"]

    if hasattr(conversation_field, "json_schema_extra"):
        assert conversation_field.json_schema_extra is not None
    if hasattr(response_field, "json_schema_extra"):
        assert response_field.json_schema_extra is not None


async def test_optimized_dspy_basic(
    dspy_func: Callable, conversation: str, expected_response: str
) -> None:
    """Shared test for basic DSPy functionality."""

    async def mock_generator(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response=expected_response)

    def mock_streamify(*args, **kwargs):
        return mock_generator

    with patch("dspy.streamify", mock_streamify):
        responses = []
        async for response in dspy_func(conversation):
            responses.append(response)

        assert len(responses) > 0
        assert hasattr(responses[0], "final_response")


async def test_optimized_dspy_empty_conversation(dspy_func: Callable, expected_response: str) -> None:
    """Shared test for empty conversation handling."""

    async def mock_generator(*args, **kwargs):
        from dspy import Prediction

        yield Prediction(final_response=expected_response)

    def mock_streamify(*args, **kwargs):
        return mock_generator

    with patch("dspy.streamify", mock_streamify):
        responses = []
        async for response in dspy_func(""):
            responses.append(response)

        assert len(responses) > 0


def test_model_config_validation(model_config_class: Type) -> None:
    """Shared test for ModelConfig validation."""
    config = model_config_class()
    assert config.truncation_length >= 1000
    assert config.timeout_seconds >= 1.0
    assert config.max_iterations <= 10

    with pytest.raises(ValueError):
        model_config_class(truncation_length=500)

    with pytest.raises(ValueError):
        model_config_class(timeout_seconds=0.5)

    with pytest.raises(ValueError):
        model_config_class(max_iterations=15)


def test_truncate_long_history_with_config(
    truncate_func: Callable, model_config_class: Type, agent_name: str
) -> None:
    """Shared test for truncate_long_history with custom config."""
    long_conversation = "\n".join(
        [
            f"User: This is {agent_name} question {i}\n{agent_name}Agent: This is response {i}"
            for i in range(50)
        ]
    )

    config = model_config_class(truncation_length=1200)
    result = truncate_func(long_conversation, config)

    assert result["truncated"]
    lines = result["history"].split("\n")
    assert len(lines) == 30
    assert "question 49" in result["history"]


def test_truncate_long_history_return_structure(truncate_func: Callable) -> None:
    """Shared test for truncate_long_history return structure."""
    result = truncate_func("Short text")

    assert "history" in result
    assert "truncated" in result
    assert "original_length" in result
    assert "truncated_length" in result
    assert isinstance(result["truncated"], bool)
    assert isinstance(result["original_length"], int)
    assert isinstance(result["truncated_length"], int)