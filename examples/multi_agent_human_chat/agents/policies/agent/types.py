"""
Type definitions for the Policies Agent.

This module contains all type definitions used throughout the policies agent code,
providing consistent typing and improving code maintainability.
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

# Type alias for policy categories
PolicyCategory = Literal["auto", "life", "home", "health"]


class ChatMessage(TypedDict, total=False):
    """Type definition for a chat message."""

    content: str  # Required message content
    role: str  # Typically "User" or "PoliciesAgent", optional with default "User"


class ModelConfig(BaseModel):
    """Configuration for the policies DSPy model."""

    name: str = Field("policies_react", description="Name of the model")
    max_iterations: int = Field(
        5, description="Maximum iterations for the model", ge=1, le=10
    )
    use_tracing: bool = Field(True, description="Whether to trace model execution")
    date_format: str = Field(
        "YYYY-MM-DD", description="Required date format for responses"
    )
    cache_enabled: bool = Field(False, description="Whether to enable model caching")
    truncation_length: int = Field(
        15000, description="Maximum length for conversation history", ge=1000
    )
    timeout_seconds: float = Field(
        30.0, description="Timeout for model inference in seconds", ge=1.0
    )
