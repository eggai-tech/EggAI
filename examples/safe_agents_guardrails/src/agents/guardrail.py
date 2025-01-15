from guardrails import Guard
from guardrails.hub import ToxicLanguage, DetectPII

toxic_pipeline = Guard().use(
    ToxicLanguage(
        threshold=0.8,
        validation_method="sentence",
        on_fail="noop"
    )
)

pii_pipeline = Guard().use(
    DetectPII, ["EMAIL_ADDRESS", "PHONE_NUMBER"], "fix"
)

def guard(text: str):
    validation = toxic_pipeline.validate(text)
    if validation.validation_passed is False:
        return None
    validation = pii_pipeline.validate(text)
    if validation.validation_passed is False:
        return None
    return validation.validated_output


if __name__ == "__main__":
    print(guard("What is the year of birth of David Gregory of Kinnairdy castle plus the year of birth of Michael Jackson?"))
    print(guard("Are you stupid?"))
    print(guard("My email is johnny@gmail.com"))
