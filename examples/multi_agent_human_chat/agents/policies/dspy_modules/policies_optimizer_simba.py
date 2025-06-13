"""
SIMBA optimizer for Policies Agent.

This script optimizes the Policies Agent using SIMBA, which typically provides
better performance than COPRO, especially for complex reasoning tasks.

Usage:
    python -m agents.policies.dspy_modules.policies_optimizer_simba
"""

from pathlib import Path
from typing import Literal

import dspy
from sklearn.model_selection import train_test_split

from agents.policies.config import settings
from agents.policies.dspy_modules.policies_dataset import (
    as_dspy_examples,
    create_policies_dataset,
)

# Direct use of dspy.SIMBA
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct

logger = get_console_logger("policies_optimizer_simba")

# Type definitions
PolicyCategory = Literal["auto", "life", "home", "health"]

# Import the signature from the main agent module
from agents.policies.dspy_modules.policies import PolicyAgentSignature


# Mock tools for optimization
def take_policy_by_number_from_database(policy_number: str):
    """Retrieve policy details from the database using the policy number."""
    return (
        '{"policy_number": "'
        + policy_number
        + '", "name": "John Doe", "policy_category": "auto", "premium_amount": 500, "due_date": "2025-06-15"}'
    )


def query_policy_documentation(query: str, policy_category: str):
    """Query the policy documentation for specific information."""
    return (
        '[{"category": "'
        + policy_category
        + '", "section": "2.1", "content": "Coverage details for '
        + query
        + '"}]'
    )


def precision_metric(example, pred, trace=None) -> float:
    """
    Calculate precision score by comparing expected and predicted responses.

    Args:
        example: Example with expected output
        pred: Model prediction
        trace: Optional trace information

    Returns:
        float: Score between 0.0 and 1.0
    """
    expected = getattr(example, "final_response", "").lower()
    predicted = getattr(pred, "final_response", "").lower()

    if not expected or not predicted:
        return 0.0

    # For privacy requests, check for standard response
    if "need your policy number" in expected:
        return 1.0 if "need your policy number" in predicted else 0.0

    # Initialize scoring
    score = 0.0
    total_checks = 0

    # Check for policy numbers (format: letter followed by numbers)
    policy_numbers = [
        word
        for word in expected.split()
        if len(word) >= 2 and word[0].isalpha() and any(c.isdigit() for c in word)
    ]
    for policy in policy_numbers:
        total_checks += 1
        if policy in predicted:
            score += 1.0

    # Check for premium amount
    if "$" in expected:
        total_checks += 1
        try:
            amount_expected = expected.split("$")[1].split(" ")[0].strip().rstrip(".")
            if "$" in predicted and amount_expected in predicted:
                score += 1.0
        except (IndexError, ValueError):
            pass

    # Check for date
    if "due on" in expected:
        total_checks += 1
        try:
            date_expected = expected.split("due on")[1].split(".")[0].strip()
            if "due on" in predicted and date_expected in predicted:
                score += 1.0
        except (IndexError, ValueError):
            pass

    # Check for documentation references
    doc_refs = [word for word in expected.split() if "#" in word]
    for ref in doc_refs:
        total_checks += 1
        if ref in predicted:
            score += 1.0

    # If no specific checks were made, compare general similarity
    if total_checks == 0:
        common_words_expected = set(expected.split())
        common_words_predicted = set(predicted.split())
        intersection = len(common_words_expected.intersection(common_words_predicted))

        if intersection >= 0.6 * len(common_words_expected):
            return 1.0
        elif intersection >= 0.3 * len(common_words_expected):
            return 0.5
        return 0.0

    # Calculate final score
    return score / total_checks


def main():
    """Run the SIMBA optimization process."""
    # Initialize language model
    dspy_set_language_model(settings)

    # Create datasets
    logger.info("Creating policies dataset...")
    raw_examples = create_policies_dataset()
    examples = as_dspy_examples(raw_examples)

    # Split dataset
    logger.info(f"Created {len(examples)} examples, splitting into train/test...")
    train_set, _ = train_test_split(examples, test_size=0.2, random_state=42)

    # Limit dataset size for faster optimization - use smaller values
    max_train = 5

    if len(train_set) > max_train:
        logger.info(f"Limiting training set to {max_train} examples")
        train_set = train_set[:max_train]

    # Create agent for optimization
    agent = TracedReAct(
        PolicyAgentSignature,
        tools=[take_policy_by_number_from_database, query_policy_documentation],
        name="policies_react",
        tracer=None,  # No tracing during optimization
        max_iters=5,
    )

    # Output path
    output_path = Path(__file__).resolve().parent / "optimized_policies_simba.json"

    # Run optimization with SIMBA - use smaller steps and demos
    logger.info("Starting SIMBA optimization with minimal parameters...")
    # Use a smaller batch size for faster optimization
    batch_size = min(4, len(train_set))  # Smaller batch size
    logger.info(f"Using batch size of {batch_size} for {len(train_set)} examples")
    simba = dspy.SIMBA(
        metric=precision_metric,
        max_steps=3,  # Reduced from 8 to 3
        max_demos=2,  # Reduced from 5 to 2
        bsize=batch_size,
    )
    optimized_agent = simba.compile(agent, trainset=train_set, seed=42)

    # Save the optimized agent
    optimized_agent.save(str(output_path))

    logger.info(f"Optimization complete! Model saved to {output_path}")


if __name__ == "__main__":
    main()
