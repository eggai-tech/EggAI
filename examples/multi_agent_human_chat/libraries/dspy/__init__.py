"""
DSPy utility modules for EggAI agents.

This package contains various utilities for working with DSPy modules in EggAI agents.
"""

from libraries.dspy.simba import load_optimized_model, optimize_with_simba

__all__ = [
    "optimize_with_simba",
    "load_optimized_model",
]