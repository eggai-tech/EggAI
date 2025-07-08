"""
Core utilities and base classes for EggAI agents.

This module provides fundamental building blocks used across all agents.
"""

from .config import BaseAgentConfig
from .models import ModelConfig, ModelResult
from .patches import patch_usage_tracker

__all__ = [
    "BaseAgentConfig",
    "ModelConfig",
    "ModelResult",
    "patch_usage_tracker",
]