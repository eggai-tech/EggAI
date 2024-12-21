from typing import Optional

from litellm import acompletion

from eggai import Agent


class LlmAgent(Agent):
    def __init__(self, name: str, model: Optional[str] = None, system_message: Optional[str] = None):
        super().__init__(name)
        self.model = model
        self.system_message = system_message

    def completion(self, *args, **kwargs):
        model = kwargs.pop("model", self.model)
        if model is None:
            raise ValueError("Model is required for completion.")

        messages = kwargs.pop("messages", [])
        if self.system_message:
            messages = [{"role": "system", "content": self.system_message}, *messages]

        return acompletion(*args, **{**kwargs, "model": model, "messages": messages})