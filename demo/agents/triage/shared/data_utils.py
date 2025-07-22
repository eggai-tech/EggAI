"""Shared data utilities for all triage classifiers."""

from typing import List

import dspy
import numpy as np

from agents.triage.data_sets.loader import load_dataset_triage_training


def create_training_examples(sample_size: int, seed: int = 42) -> List[dspy.Example]:
    """Create training examples with deterministic sampling for reproducible results.
    
    Args:
        sample_size: Number of examples to sample. Use -1 for all examples.
        seed: Random seed for reproducible sampling.
        
    Returns:
        List of DSPy examples for training.
    """
    training_data = load_dataset_triage_training()
    total_available = len(training_data)
    
    if sample_size == -1:
        actual_size = total_available
    elif sample_size > total_available:
        actual_size = total_available
    else:
        actual_size = sample_size
        # Use numpy for deterministic sampling
        rs = np.random.RandomState(seed)
        keys = rs.choice(len(training_data), size=actual_size, replace=False)
        training_data = [training_data[i] for i in keys]
    
    print(f"Using {actual_size}/{total_available} examples")
    
    examples = []
    for case in training_data:
        target_agent = case.target_agent
        if hasattr(target_agent, 'value'):
            target_agent = target_agent.value
        
        examples.append(dspy.Example(
            chat_history=case.conversation,
            target_agent=target_agent
        ).with_inputs("chat_history"))
    
    return examples