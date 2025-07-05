from guardrails import AsyncGuard

from libraries.logger import get_console_logger

logger = get_console_logger("frontend_agent")

try:
    from guardrails.hub import ToxicLanguage
except ImportError:
    logger.warning("ToxicLanguage validator not found in guardrails.hub; disabling guardrails")
    ToxicLanguage = None

_toxic_language_guard = None
if ToxicLanguage:
    _toxic_language_guard = AsyncGuard().use(
        ToxicLanguage,
        threshold=0.5,
        validation_method="sentence",
        on_fail="noop",
    )


async def toxic_language_guard(text: str) -> str | None:
    """
    Validate and filter text via ToxicLanguage guardrail.

    Returns the sanitized text if passed, otherwise None.
    If ToxicLanguage is unavailable, returns text unchanged.
    """
    if _toxic_language_guard is None:
        return text
    result = await _toxic_language_guard.validate(text)
    if result.validation_passed is False:
        return None
    return result.validated_output
