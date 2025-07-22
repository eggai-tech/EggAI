"""Data utilities for classifier v6."""

from typing import List

import dspy

from agents.triage.shared.data_utils import (
    create_training_examples as _create_training_examples,
)


def create_training_examples(sample_size: int = 20, seed: int = 42) -> List[dspy.Example]:
    """Create training examples for v6 classifier with default sample size of 20.
    
    Args:
        sample_size: Number of examples to sample (default: 20 for cost-effective OpenAI fine-tuning)
        seed: Random seed for reproducible sampling
        
    Returns:
        List of DSPy examples for training
    """
    return _create_training_examples(sample_size=sample_size, seed=seed)