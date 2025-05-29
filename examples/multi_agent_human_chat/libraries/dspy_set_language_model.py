from time import perf_counter
from typing import Optional

import dspy
from dotenv import load_dotenv


class TrackingLM(dspy.LM):
    def __init__(self, *args, **kwargs):
        # Handle special parameters for specific providers
        model_name = args[0] if args else ""
        self.is_lm_studio = "lm_studio" in model_name or "lm-studio" in model_name

        if self.is_lm_studio:
            # Remove response_format for LM Studio
            kwargs.pop("response_format", None)
            # Set default max context window for LM Studio
            self.max_context_window = 128000
        else:
            # Default max context window for other models
            self.max_context_window = 16384

        super().__init__(*args, **kwargs)
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0
        self.run_logs = []
        self.model_name = model_name

    def __call__(self, *args, **kwargs):
        self.start_run()
        start_time = perf_counter()
        res = super().__call__(*args, **kwargs)
        self.latency_ms = (perf_counter() - start_time) * 1000
        return res

    def start_run(self):
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0

    def _truncate_prompt(self, prompt, max_length=None):
        """Truncate a prompt to fit within the model's context window."""
        if prompt is None:
            return None

        # Estimate token count very roughly (avg 4 chars per token)
        estimated_tokens = len(prompt) / 4
        max_tokens = max_length or self.max_context_window

        # Reserve 20% of context for completion
        available_tokens = int(max_tokens * 0.8)

        if estimated_tokens > available_tokens:
            # Simple truncation strategy - keep the most recent parts
            # More sophisticated methods could preserve the system prompt
            truncation_ratio = available_tokens / estimated_tokens
            # Keep the last part of the conversation
            keep_chars = int(len(prompt) * truncation_ratio)
            return "..." + prompt[-keep_chars:]
        return prompt

    def _truncate_messages(self, messages, max_length=None):
        """Truncate a messages list to fit within the model's context window."""
        if not messages:
            return messages

        max_tokens = max_length or self.max_context_window
        # Reserve 20% of context for completion
        available_tokens = int(max_tokens * 0.8)

        # Estimate tokens very roughly
        total_estimated_tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            total_estimated_tokens += (
                len(content) / 4 + 20
            )  # 20 extra tokens for role and formatting

        # If within limits, return as is
        if total_estimated_tokens <= available_tokens:
            return messages

        # Otherwise, we need to truncate
        result_messages = []

        # Always keep the system message if present
        if messages and messages[0].get("role") == "system":
            result_messages.append(messages[0])
            messages = messages[1:]

        # Keep more recent messages, drop older ones in the middle
        if len(messages) > 4:
            # Keep the most recent exchanges (the last 4 messages)
            result_messages.extend(messages[-4:])
        else:
            result_messages.extend(messages)

        return result_messages

    def forward(self, prompt=None, messages=None, **kwargs):
        # Remove incompatible parameters for specific providers
        if self.is_lm_studio:
            # LM Studio doesn't support response_format
            kwargs.pop("response_format", None)

            # Handle context length for LM Studio
            if prompt:
                prompt = self._truncate_prompt(prompt, self.max_context_window)
            if messages:
                messages = self._truncate_messages(messages, self.max_context_window)

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
        api_base=settings.language_model_api_base
        if settings.language_model_api_base
        else None,
    )

    # Configure max context window if specified
    if hasattr(settings, "max_context_window") and settings.max_context_window:
        language_model.max_context_window = settings.max_context_window

    # Debugging info
    from libraries.logger import get_console_logger

    logger = get_console_logger("dspy_language_model")
    logger.info(f"Configured language model: {settings.language_model}")
    logger.info(f"Max context window: {language_model.max_context_window}")
    logger.info(f"LM Studio model: {language_model.is_lm_studio}")

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
        entities: list[dict[str, str]] = dspy.OutputField(
            desc="a list of entities and their metadata"
        )

    module = dspy.Predict(ExtractInfo)

    text = (
        "Apple Inc. announced its latest iPhone 14 today."
        "The CEO, Tim Cook, highlighted its new features in a press release."
    )
    response = module(text=text)

    print("Tokens printed: ", lm.total_tokens, lm.prompt_tokens, lm.completion_tokens)

    text = (
        "Microsoft Corporation is a technology company based in Redmond, Washington."
        "The company was founded by Bill Gates and Paul Allen in 1975."
    )
    r = module(text=text)

    print("Tokens printed: ", lm.total_tokens, lm.prompt_tokens, lm.completion_tokens)
