"""Shared data utilities for all triage classifiers."""

from typing import List

import dspy
import numpy as np

from agents.triage.data_sets.loader import (
    load_dataset_triage_testing,
    load_dataset_triage_training,
)


def create_examples(sample_size: int = -1, phase: str = "train", seed: int = 42) -> List[dspy.Example]:
    """Create training examples with deterministic sampling for reproducible results.
    
    Args:
        sample_size: Number of examples to sample. Use -1 for all examples.
        phase: either "train" or "test". Determines which dataset to load.
        seed: Random seed for reproducible sampling.
        
    Returns:
        List of DSPy examples for training.
    """
    if phase not in ["train", "test"]:
        raise ValueError(f"Invalid phase: {phase}. Expected 'train' or 'test'.")
    if phase == "test":
        dataset = load_dataset_triage_testing()
    else:
        dataset = load_dataset_triage_training()
    total_available = len(dataset)

    if sample_size == -1:
        actual_size = total_available
    elif sample_size > total_available:
        actual_size = total_available
    else:
        actual_size = sample_size
        # Use deterministic sampling
        rs = np.random.RandomState(seed)
        keys = rs.choice(len(dataset), size=actual_size, replace=False)
        dataset = [dataset[i] for i in keys]

    print(f"Using {actual_size}/{total_available} examples")

    examples = []
    for case in dataset:
        target_agent = case.target_agent
        if hasattr(target_agent, 'value'):
            target_agent = target_agent.value

        examples.append(dspy.Example(
            chat_history=case.conversation,
            target_agent=target_agent
        ).with_inputs("chat_history"))

    return examples
