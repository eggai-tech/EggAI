"""Tests for configuration loading and guardrails integration."""

import os

import pytest

from .. import guardrails as guardrails_mod
from ..config import Settings


def test_settings_defaults():
    """Ensure Settings defaults match expected values."""
    s = Settings()
    # Server defaults
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.log_level == "info"
    # Kafka defaults
    assert s.kafka_bootstrap_servers == "localhost:19092"
    assert s.kafka_topic_prefix == "eggai"
    # Observability defaults
    assert s.tracing_enabled is True
    assert isinstance(s.prometheus_metrics_port, int)


def test_default_public_dir_property(monkeypatch, tmp_path):
    """Test default_public_dir points to the public folder when not set."""
    # Ensure PUBLIC_DIR not set
    monkeypatch.delenv("FRONTEND_PUBLIC_DIR", raising=False)
    s = Settings()
    default_dir = s.default_public_dir
    assert default_dir.endswith(os.path.join('agents', 'frontend', 'public'))


def test_override_public_dir(monkeypatch):
    """Test that setting FRONTEND_PUBLIC_DIR overrides default_public_dir."""
    custom = "/tmp/custom_public"
    monkeypatch.setenv("FRONTEND_PUBLIC_DIR", custom)
    s = Settings()
    assert s.default_public_dir == custom


@pytest.mark.asyncio
async def test_toxic_language_guard_pass(monkeypatch):
    """Guardrails should return validated_output when validation_passed is True."""
    class DummyResult:
        validation_passed = True
        validated_output = "cleaned"

    async def dummy_validate(text):
        return DummyResult()

    monkeypatch.setattr(guardrails_mod, '_toxic_language_guard',
                        type('X', (), {'validate': dummy_validate})())
    out = await guardrails_mod.toxic_language_guard("input text")
    assert out == "cleaned"


@pytest.mark.asyncio
async def test_toxic_language_guard_fail(monkeypatch):
    """Guardrails should return None when validation_passed is False."""
    class DummyResult:
        validation_passed = False
        validated_output = "irrelevant"

    async def dummy_validate(text):
        return DummyResult()

    monkeypatch.setattr(guardrails_mod, '_toxic_language_guard',
                        type('X', (), {'validate': dummy_validate})())
    out = await guardrails_mod.toxic_language_guard("toxic text")
    assert out is None