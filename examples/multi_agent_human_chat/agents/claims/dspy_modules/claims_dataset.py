"""Dataset generator for Claims Agent optimization."""
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List

import dspy

from libraries.logger import get_console_logger

logger = get_console_logger("claims_agent.dataset")


@dataclass
class ClaimsExample:
    """Example for Claims Agent dataset."""
    chat_history: str
    expected_response: str


def create_claims_dataset() -> List[ClaimsExample]:
    """Create a dataset of claims examples.
    
    Returns:
        List[ClaimsExample]: A list of examples for claims scenarios.
    """
    # Known claims data from the mock database
    claims_data = [
        {
            "claim_number": "1001",
            "policy_number": "A12345",
            "status": "In Review",
            "estimate": 2300.0,
            "estimate_date": "2026-05-15",
            "next_steps": "Submit repair estimates",
            "outstanding_items": ["Repair estimates"]
        },
        {
            "claim_number": "1002",
            "policy_number": "B67890",
            "status": "Approved",
            "estimate": 1500.0,
            "estimate_date": "2026-04-20",
            "next_steps": "Processing payment",
            "outstanding_items": []
        },
        {
            "claim_number": "1003",
            "policy_number": "C24680",
            "status": "Pending Documentation",
            "estimate": None,
            "estimate_date": None,
            "next_steps": "Upload photos and police report",
            "outstanding_items": ["Photos", "Police report"]
        },
    ]
    
    logger.info("Creating claims dataset examples")
    examples = []
    
    # Claim status inquiries
    for claim in claims_data:
        chat = f"""User: I want to check my claim status.
ClaimsAgent: I'd be happy to help you check your claim status. Could you please provide your claim number?
User: It's {claim["claim_number"]}."""
        
        estimate_text = f"${claim['estimate']:.2f}" if claim['estimate'] else "pending assessment"
        estimate_date_text = f"by {claim['estimate_date']}" if claim['estimate_date'] else ""
        
        outstanding_items_text = ""
        if claim["outstanding_items"]:
            items_list = ", ".join(claim["outstanding_items"])
            outstanding_items_text = f"We're still awaiting your {items_list}—please submit them at your earliest convenience."
        
        expected = f"Your claim #{claim['claim_number']} is currently '{claim['status']}'. "
        if claim['estimate'] is not None:
            expected += f"We estimate a payout of {estimate_text} {estimate_date_text}. "
        expected += outstanding_items_text
        
        examples.append(ClaimsExample(
            chat_history=chat,
            expected_response=expected.strip()
        ))
    
    # Filing new claim inquiries
    policy_numbers = ["A12345", "B67890", "C24680"]
    incident_types = [
        "car accident",
        "home water damage",
        "stolen electronics",
        "hurricane damage",
        "vandalism to vehicle"
    ]
    
    for policy in policy_numbers:
        for incident in random.sample(incident_types, 2):  # Each policy gets 2 random incidents
            chat = f"""User: I need to file a new claim.
ClaimsAgent: I'd be happy to help you file a new claim. Could you please provide your policy number and details about the incident?
User: My policy number is {policy}, and I had a {incident} yesterday."""
            
            expected = f"I've filed a new claim under policy {policy}. " + \
                      "Please upload photos of the damage and any police report within 5 business days to expedite processing."
            
            examples.append(ClaimsExample(
                chat_history=chat,
                expected_response=expected
            ))
    
    # Updating claim information inquiries
    fields_to_update = ["address", "phone", "damage_description", "incident date"]
    new_values = {
        "address": "123 Main St, Anytown, USA",
        "phone": "555-123-4567",
        "damage_description": "more extensive than initially reported",
        "incident date": "January 15, 2026"
    }
    
    for claim in claims_data:
        for field in random.sample(fields_to_update, 2):  # Each claim gets 2 random field updates
            chat = f"""User: I need to update information on my claim.
ClaimsAgent: I'd be happy to help you update your claim information. Could you please provide your claim number?
User: It's {claim["claim_number"]}.
ClaimsAgent: What information would you like to update?
User: I need to change the {field}."""
            
            # For first interaction, ask for the new value
            expected = f"What is the new {field} you'd like to update on your claim?"
            
            examples.append(ClaimsExample(
                chat_history=chat,
                expected_response=expected
            ))
            
            # Add a follow-up example with the new value provided
            follow_up_chat = chat + f"\nClaimsAgent: {expected}\nUser: The new {field} is {new_values[field]}."
            
            follow_up_expected = f"I've updated the {field} to '{new_values[field]}' on claim #{claim['claim_number']} as requested."
            
            examples.append(ClaimsExample(
                chat_history=follow_up_chat,
                expected_response=follow_up_expected
            ))
    
    logger.info(f"Created {len(examples)} claims dataset examples")
    return examples


def as_dspy_examples(examples: List[ClaimsExample]) -> List[dspy.Example]:
    """Convert ClaimsExample objects to dspy.Example objects.
    
    Args:
        examples (List[ClaimsExample]): List of claims examples.
        
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
    logger.info(f"Converted {len(dspy_examples)} examples to DSPy format")
    return dspy_examples


def export_dataset(examples: List[ClaimsExample], output_path: str = None):
    """Export dataset to a JSON file.
    
    Args:
        examples: List of examples to export
        output_path: Path to save JSON file (defaults to module directory)
    """
    if not output_path:
        output_path = Path(__file__).resolve().parent / "claims_dataset.json"
        
    serialized = [
        {"chat_history": e.chat_history, "expected_response": e.expected_response}
        for e in examples
    ]
    
    try:
        with open(output_path, 'w') as f:
            json.dump(serialized, f, indent=2)
        logger.info(f"Exported {len(serialized)} examples to {output_path}")
    except Exception as e:
        logger.error(f"Error exporting dataset: {e}")


def load_dataset(input_path: str = None) -> List[ClaimsExample]:
    """Load dataset from a JSON file.
    
    Args:
        input_path: Path to load JSON file from (defaults to module directory)
        
    Returns:
        List[ClaimsExample]: Loaded examples
    """
    if not input_path:
        input_path = Path(__file__).resolve().parent / "claims_dataset.json"
    
    if not os.path.exists(input_path):
        logger.warning(f"Dataset file not found at {input_path}, creating new dataset")
        return create_claims_dataset()
        
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
            
        examples = [
            ClaimsExample(
                chat_history=item["chat_history"],
                expected_response=item["expected_response"]
            )
            for item in data
        ]
        logger.info(f"Loaded {len(examples)} examples from {input_path}")
        return examples
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        return create_claims_dataset()


if __name__ == "__main__":
    # Generate examples and print them
    examples = create_claims_dataset()
    print(f"Generated {len(examples)} examples")
    
    # Export examples to JSON
    export_dataset(examples)
    
    # Print a sample
    random.seed(42)
    sample = random.sample(examples, min(3, len(examples)))
    for i, example in enumerate(sample):
        print(f"\nExample {i+1}:")
        print(f"Chat history:\n{example.chat_history}")
        print(f"Expected response:\n{example.expected_response}")