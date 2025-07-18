"""
Machine Learning utilities for EggAI agents.

This module provides ML-related functionality including DSPy integration,
device management, and MLflow utilities.
"""

from .device import get_device

__all__ = [
    "get_device",
]