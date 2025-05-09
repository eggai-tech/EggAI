from time import perf_counter
from typing import Optional

import dspy
from dotenv import load_dotenv

class TrackingLM(dspy.LM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0
        self.run_logs = []

    def __call__(self, *args, **kwargs):
        self.start_run()
        start_time = perf_counter()
        res = super().__call__(*args, **kwargs)
        self.latency_ms = (perf_counter() - start_time) * 1000
        print(f"Latency: {self.latency_ms} ms")
        return res

    def start_run(self):
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0
        print("Starting new run...")

    def forward(self, prompt=None, messages=None, **kwargs):
        forward_result = super().forward(prompt, messages, **kwargs)
        self.completion_tokens += forward_result.usage.get("completion_tokens", 0)
        self.prompt_tokens += forward_result.usage.get("prompt_tokens", 0)
        self.total_tokens += forward_result.usage.get("total_tokens", 0)
        return forward_result

def dspy_set_language_model(settings, overwrite_cache_enabled: Optional[bool] = None):
    load_dotenv()

    cache_enabled = settings.cache_enabled
    if overwrite_cache_enabled is not None:
        cache_enabled = overwrite_cache_enabled

    language_model = TrackingLM(
        settings.language_model,
        cache=cache_enabled,
        api_base=settings.language_model_api_base if settings.language_model_api_base else None,
    )

    dspy.configure(lm=language_model)

    return language_model

if __name__ == "__main__":

    # Example usage
    class Settings:
        language_model = "openai/gpt-4o-mini"
        cache_enabled = False
        language_model_api_base = None

    settings = Settings()
    lm = dspy_set_language_model(settings)

    # Test
    class ExtractInfo(dspy.Signature):
        """Extract structured information from text."""

        text: str = dspy.InputField()
        title: str = dspy.OutputField()
        headings: list[str] = dspy.OutputField()
        entities: list[dict[str, str]] = dspy.OutputField(desc="a list of entities and their metadata")


    module = dspy.Predict(ExtractInfo)

    text = "Apple Inc. announced its latest iPhone 14 today." \
           "The CEO, Tim Cook, highlighted its new features in a press release."
    response = module(text=text)

    print("Tokens printed: ", lm.total_tokens, lm.prompt_tokens, lm.completion_tokens)

    text = "Microsoft Corporation is a technology company based in Redmond, Washington." \
              "The company was founded by Bill Gates and Paul Allen in 1975."
    r = module(text=text)

    print("Tokens printed: ", lm.total_tokens, lm.prompt_tokens, lm.completion_tokens)