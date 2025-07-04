import pytest

from agents.triage.agent import (
    _CLASSIFIER_PATHS,
    build_conversation_string,
    get_current_classifier,
)
from agents.triage.config import settings


def test_build_conversation_string_empty():
    # No messages yields empty string
    assert build_conversation_string([]) == ""


def test_build_conversation_string_basic():
    msgs = [
        {"agent": "User", "content": "Hello"},
        {"agent": "Bot", "content": "Hi there!"},
    ]
    expected = "User: Hello\nBot: Hi there!\n"
    assert build_conversation_string(msgs) == expected


def test_build_conversation_string_filters_empty_content():
    msgs = [
        {"agent": "User", "content": ""},
        {"agent": "Bot", "content": "Response"},
    ]
    expected = "Bot: Response\n"
    assert build_conversation_string(msgs) == expected


@pytest.mark.parametrize("version,module_fn", list(_CLASSIFIER_PATHS.items()))
def test_get_current_classifier_valid(monkeypatch, version, module_fn):
    # Ensure get_current_classifier returns a callable for each supported version
    monkeypatch.setattr(settings, "classifier_version", version)
    fn = get_current_classifier()
    assert callable(fn)


def test_get_current_classifier_invalid(monkeypatch):
    # Unsupported version should raise ValueError
    monkeypatch.setattr(settings, "classifier_version", "nonexistent")
    with pytest.raises(ValueError):
        get_current_classifier()