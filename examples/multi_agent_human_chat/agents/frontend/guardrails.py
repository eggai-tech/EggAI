"""Guardrails for content moderation."""

from guardrails import AsyncGuard
from guardrails.hub import ToxicLanguage

from libraries.logger import get_console_logger

from .types import GuardrailsConfig

logger = get_console_logger("frontend_agent")

# Default configuration
default_config = GuardrailsConfig(
    enabled=True, toxic_language_threshold=0.5, validation_method="sentence"
)

_toxic_language_guard = AsyncGuard().use(
    ToxicLanguage,
    threshold=default_config.toxic_language_threshold,
    validation_method=default_config.validation_method,
    on_fail="noop",
)


async def toxic_language_guard(text: str):
    result = await _toxic_language_guard.validate(text)
    if result.validation_passed is False:
        return None
    return result.validated_output
