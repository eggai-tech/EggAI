"""Dataset generator for Billing Agent optimization."""
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Any

import dspy


@dataclass
class BillingExample:
    """Example for Billing Agent dataset."""
    chat_history: str
    expected_response: str


def create_billing_dataset() -> List[BillingExample]:
    """Create a dataset of billing examples.
    
    Returns:
        List[BillingExample]: A list of examples for billing scenarios.
    """
    # Known policy data from the mock database
    billing_data = [
        {
            "policy_number": "A12345",
            "billing_cycle": "Monthly",
            "amount_due": 120.0,
            "due_date": "2025-02-01",
            "status": "Paid",
        },
        {
            "policy_number": "B67890",
            "billing_cycle": "Quarterly",
            "amount_due": 300.0,
            "due_date": "2025-03-15",
            "status": "Pending",
        },
        {
            "policy_number": "C24680",
            "billing_cycle": "Annual",
            "amount_due": 1000.0,
            "due_date": "2025-12-01",
            "status": "Pending",
        },
    ]
    
    examples = []
    
    # Payment due date inquiries
    for policy in billing_data:
        chat = f"""User: When is my next payment due?
BillingAgent: I'd be happy to help you with that. Could you please provide your policy number?
User: It's {policy["policy_number"]}."""
        
        expected = f"Your next payment of ${policy['amount_due']:.2f} is due on {policy['due_date']}, and your current status is '{policy['status']}'."
        
        examples.append(BillingExample(
            chat_history=chat,
            expected_response=expected
        ))
    
    # Amount due inquiries
    for policy in billing_data:
        chat = f"""User: How much do I owe on my policy?
BillingAgent: I'd be happy to check that for you. Could you please provide your policy number?
User: {policy["policy_number"]}"""
        
        expected = f"Your current amount due is ${policy['amount_due']:.2f} with a due date of {policy['due_date']}. Your status is '{policy['status']}'."
        
        examples.append(BillingExample(
            chat_history=chat,
            expected_response=expected
        ))
    
    # Billing cycle inquiries
    for policy in billing_data:
        chat = f"""User: What's my billing cycle?
BillingAgent: I can check that for you. May I have your policy number please?
User: {policy["policy_number"]}"""
        
        expected = f"Your current billing cycle is '{policy['billing_cycle']}' with the next payment of ${policy['amount_due']:.2f} due on {policy['due_date']}."
        
        examples.append(BillingExample(
            chat_history=chat,
            expected_response=expected
        ))
    
    # Payment status inquiries
    for policy in billing_data:
        chat = f"""User: Has my payment gone through?
BillingAgent: I can check that for you. Could you please provide your policy number?
User: {policy["policy_number"]}"""
        
        if policy["status"] == "Paid":
            expected = f"Yes, your payment has been processed successfully. Your account is marked as '{policy['status']}' for the payment due on {policy['due_date']}."
        else:
            expected = f"Your payment status for the amount of ${policy['amount_due']:.2f} due on {policy['due_date']} is currently '{policy['status']}'."
        
        examples.append(BillingExample(
            chat_history=chat,
            expected_response=expected
        ))
    
    return examples


def as_dspy_examples(examples: List[BillingExample]) -> List[dspy.Example]:
    """Convert BillingExample objects to dspy.Example objects.
    
    Args:
        examples (List[BillingExample]): List of billing examples.
        
    Returns:
        List[dspy.Example]: List of dspy.Example objects.
    """
    dspy_examples = []
    for example in examples:
        dspy_examples.append(
            dspy.Example(
                chat_history=example.chat_history,
                final_response=example.expected_response,
            ).with_inputs("chat_history")
        )
    return dspy_examples


if __name__ == "__main__":
    # Generate examples and print them
    examples = create_billing_dataset()
    print(f"Generated {len(examples)} examples")
    
    # Print a sample
    random.seed(42)
    sample = random.sample(examples, min(3, len(examples)))
    for i, example in enumerate(sample):
        print(f"\nExample {i+1}:")
        print(f"Chat history:\n{example.chat_history}")
        print(f"Expected response:\n{example.expected_response}")