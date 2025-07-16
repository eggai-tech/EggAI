from typing import Optional

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    name: str = Field(
        default="base_model",
        description="Name of the model or reasoning chain"
    )
    max_iterations: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of iterations for the model"
    )
    use_tracing: bool = Field(
        default=True,
        description="Whether to trace model execution for debugging"
    )
    cache_enabled: bool = Field(
        default=False,
        description="Whether to enable model result caching"
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        description="Timeout for model inference in seconds"
    )
    truncation_length: int = Field(
        default=15000,
        ge=1000,
        description="Maximum length for conversation history before truncation"
    )

    model_config = {"validate_assignment": True}


class ModelResult(BaseModel):
    response: str = Field(
        ...,
        description="The generated response text"
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds"
    )
    success: bool = Field(
        default=True,
        description="Whether the model execution was successful"
    )
    truncated: bool = Field(
        default=False,
        description="Whether the input was truncated"
    )
    original_length: Optional[int] = Field(
        default=None,
        description="Original length of input before truncation"
    )
    truncated_length: Optional[int] = Field(
        default=None,
        description="Length of input after truncation"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )

    model_config = {"validate_assignment": True}