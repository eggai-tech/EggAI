
import random
from typing import List

import dspy

from agents.triage.data_sets.loader import load_dataset_triage_training


def create_training_examples(sample_size: int = 20) -> List[dspy.Example]:
    training_data = load_dataset_triage_training()
    total_available = len(training_data)
    
    if sample_size == -1:
        actual_size = total_available
    elif sample_size > total_available:
        actual_size = total_available
    else:
        actual_size = sample_size
        training_data = random.sample(training_data, actual_size)
    
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