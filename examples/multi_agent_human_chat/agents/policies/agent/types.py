from typing import Literal

from pydantic import Field

from libraries.types import (
    ChatMessage as ChatMessage,
)
from libraries.types import (
    ModelConfig as BaseModelConfig,
)

PolicyCategory = Literal["auto", "life", "home", "health"]


class PoliciesModelConfig(BaseModelConfig):
    """Policies agent-specific model configuration."""

    name: str = Field("policies_react", description="Name of the model")
    date_format: str = Field("YYYY-MM-DD", description="Required date format for responses")

ModelConfig = PoliciesModelConfig
