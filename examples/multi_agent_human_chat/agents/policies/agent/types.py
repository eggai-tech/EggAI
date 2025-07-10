from typing import Literal

from pydantic import Field

from libraries.communication.protocol import (
    ChatMessage as ChatMessage,
)
from libraries.core import (
    ModelConfig as BaseModelConfig,
)

PolicyCategory = Literal["auto", "life", "home", "health"]


class ModelConfig(BaseModelConfig):
    name: str = Field("policies_react", description="Name of the model")
    date_format: str = Field("YYYY-MM-DD", description="Required date format for responses")
