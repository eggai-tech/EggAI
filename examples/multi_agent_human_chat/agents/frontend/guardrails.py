from guardrails import AsyncGuard
from guardrails.hub import ToxicLanguage
from libraries.logger import get_console_logger

logger = get_console_logger("frontend_agent")

_toxic_language_guard = AsyncGuard().use(
    ToxicLanguage, threshold=0.5, validation_method="sentence", on_fail="noop"
)


async def toxic_language_guard(text: str):
    result = await _toxic_language_guard.validate(text)
    if result.validation_passed is False:
        return None
    return result.validated_output


if __name__ == "__main__":
    logger.info(toxic_language_guard("hi"))
    logger.info(toxic_language_guard("You are a stupid idiot who can't do anything right."))
