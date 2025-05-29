"""
SIMBA optimizer for Escalation Agent.

This script optimizes the Escalation Agent using SIMBA (Stochastic Introspective Mini-Batch Ascent)
to improve performance for complex reasoning tasks.

Usage:
    python -m agents.escalation.dspy_modules.escalation_optimizer_simba
"""

from pathlib import Path

import dspy
from sklearn.model_selection import train_test_split

from agents.escalation.config import settings
from agents.escalation.dspy_modules.escalation_dataset import (
    as_dspy_examples,
    create_escalation_dataset,
)

# Direct use of dspy.SIMBA
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedReAct

logger = get_console_logger("escalation_optimizer_simba")


# Create the signature for optimization
class TicketingSignature(dspy.Signature):
    """
    You are the Escalation Agent for an insurance company.

    ROLE:
    - You manage escalations and create support tickets when issues can't be resolved through normal channels
    - Guide users through the escalation process, collecting necessary information
    - Create tickets and provide reference numbers for tracking
    - Maintain a professional, empathetic tone

    WORKFLOW STAGES:
    1. Initial Assessment: Determine if the issue requires escalation
    2. Information Gathering: Collect department, issue details, and contact information
    3. Confirmation: Verify information before ticket creation
    4. Ticket Creation: Generate ticket and provide reference number
    5. Follow-up: Provide expected response time and next steps

    GUIDELINES:
    - Always ask for missing information one piece at a time
    - Verify all required information before creating a ticket
    - Provide clear confirmation when a ticket is created
    - Be empathetic but professional in your responses
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Response to the user.")


# Mock tools for optimization
def get_user_ticket_history(user_id: str):
    """Get history of tickets created by a user."""
    return '[{"id": "TICKET-001", "department": "Technical Support", "title": "Billing Issue", "status": "In Progress"}]'


def create_support_ticket(
    department: str, title: str, description: str, contact_info: str
):
    """Create a new support ticket in the system."""
    return (
        '{"ticket_id": "TICKET-123", "department": "'
        + department
        + '", "title": "'
        + title
        + '", "status": "Created", "expected_response_time": "24 hours"}'
    )


def escalation_metric(example, pred, trace=None) -> float:
    """
    Calculate accuracy for escalation agent responses.

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

    # For information request, check if we're asking for the right info
    info_requests = {
        "what department": ["department", "which department"],
        "contact information": ["email", "phone", "contact"],
        "describe issue": ["describe", "details", "about the issue"],
    }

    for key, phrases in info_requests.items():
        if key in expected:
            return 1.0 if any(p in predicted for p in phrases) else 0.0

    # For ticket creation, check if ticket ID is mentioned
    if "ticket" in expected and "created" in expected:
        if "ticket" in predicted and ("created" in predicted or "opened" in predicted):
            return 1.0
        return 0.0

    # General response similarity
    expected_words = set(expected.split())
    predicted_words = set(predicted.split())

    if not expected_words:
        return 0.0

    overlap = len(expected_words.intersection(predicted_words))
    score = overlap / len(expected_words)

    return min(1.0, score)


def main():
    """Run the SIMBA optimization process."""
    # Initialize language model
    dspy_set_language_model(settings)

    # Create datasets
    logger.info("Creating escalation dataset...")
    raw_examples = create_escalation_dataset()
    examples = as_dspy_examples(raw_examples)

    # Split dataset
    logger.info(f"Created {len(examples)} examples, splitting into train/test...")
    train_set, test_set = train_test_split(examples, test_size=0.2, random_state=42)

    # Limit dataset size for faster optimization - use smaller values
    max_train = 5
    max_test = 3

    if len(train_set) > max_train:
        logger.info(f"Limiting training set to {max_train} examples")
        train_set = train_set[:max_train]

    if len(test_set) > max_test:
        logger.info(f"Limiting test set to {max_test} examples")
        test_set = test_set[:max_test]

    # Create agent for optimization
    agent = TracedReAct(
        TicketingSignature,
        tools=[get_user_ticket_history, create_support_ticket],
        name="escalation_react",
        tracer=None,  # No tracing during optimization
        max_iters=5,
    )

    # Output path
    output_path = Path(__file__).resolve().parent / "optimized_escalation_simba.json"

    # Run optimization with SIMBA - use smaller steps and demos
    logger.info("Starting SIMBA optimization with minimal parameters...")
    # Use a smaller batch size for faster optimization
    batch_size = min(4, len(train_set))  # Smaller batch size
    logger.info(f"Using batch size of {batch_size} for {len(train_set)} examples")
    simba = dspy.SIMBA(
        metric=escalation_metric,
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
