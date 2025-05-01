import dspy
from dotenv import load_dotenv


def dspy_set_language_model(settings):
    load_dotenv()

    language_model = dspy.LM(
        settings.language_model,
        cache=settings.cache_enabled,
        api_base=settings.language_model_api_base if settings.language_model_api_base else None,
    )

    dspy.configure(lm=language_model)

    return language_model