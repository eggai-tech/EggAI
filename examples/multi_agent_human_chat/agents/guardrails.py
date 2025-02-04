from guardrails import Guard
from guardrails.hub import ToxicLanguage


_toxic_language_guard = Guard().use(
    ToxicLanguage, threshold=0.5, validation_method="sentence", on_fail="noop"
)


def toxic_language_guard(text: str):
    result = _toxic_language_guard.validate(text)
    if result.validation_passed is False:
        print("validation failed")
        return None
    return result.validated_output


if __name__ == "__main__":
    print(toxic_language_guard("hi"))
    print(toxic_language_guard("You are a stupid idiot who can't do anything right."))
