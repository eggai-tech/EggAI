"""Dataset generator for Policies Agent optimization."""
import random
from dataclasses import dataclass
from typing import List, Literal, Optional

import dspy

PolicyCategory = Literal["auto", "life", "home", "health"]


@dataclass
class PoliciesExample:
    """Example for Policies Agent dataset."""
    chat_history: str
    expected_response: str
    policy_category: Optional[PolicyCategory] = None
    policy_number: Optional[str] = None
    documentation_reference: Optional[str] = None


def create_policies_dataset() -> List[PoliciesExample]:
    """Create a dataset of policies examples.
    
    Returns:
        List[PoliciesExample]: A list of examples for policies scenarios.
    """
    # Known policies data from the mock database
    policies_data = [
        {
            "policy_number": "A12345",
            "name": "John Doe",
            "policy_category": "auto",
            "premium_amount": 500,
            "due_date": "2026-03-01",
        },
        {
            "policy_number": "B67890",
            "name": "Jane Smith",
            "policy_category": "life",
            "premium_amount": 300,
            "due_date": "2026-03-01",
        },
        {
            "policy_number": "C24680",
            "name": "Alice Johnson",
            "policy_category": "home",
            "premium_amount": 400,
            "due_date": "2026-03-01",
        },
    ]
    
    examples = []
    
    # Premium payment inquiries
    for policy in policies_data:
        chat = f"""User: When is my next premium payment due?
PoliciesAgent: I'd be happy to help you with that. Could you please provide your policy number?
User: {policy["policy_number"]}."""
        
        expected = f"Your next premium payment of ${policy['premium_amount']} for your {policy['policy_category']} policy is due on {policy['due_date']}. Is there anything else you would like to know about your policy?"
        
        examples.append(PoliciesExample(
            chat_history=chat,
            expected_response=expected,
            policy_number=policy["policy_number"],
            policy_category=policy["policy_category"]
        ))
    
    # Policy coverage inquiries with documentation references
    policy_categories = ["auto", "home", "life", "health"]
    coverage_topics = {
        "auto": ["accident coverage", "theft protection", "liability coverage", "rental car coverage"],
        "home": ["fire damage", "flood damage", "theft coverage", "liability protection"],
        "life": ["death benefit", "cash value", "premium payments", "beneficiary designation"],
        "health": ["prescription coverage", "specialist visits", "emergency care", "preventive care"]
    }
    
    # Documentation references for each category and topic
    doc_references = {
        "auto": {
            "accident coverage": "auto#2.1",
            "theft protection": "auto#3.4",
            "liability coverage": "auto#4.1", 
            "rental car coverage": "auto#5.2"
        },
        "home": {
            "fire damage": "home#2.3",
            "flood damage": "home#3.1", 
            "theft coverage": "home#4.2",
            "liability protection": "home#5.5"
        },
        "life": {
            "death benefit": "life#1.4",
            "cash value": "life#2.5",
            "premium payments": "life#3.2",
            "beneficiary designation": "life#4.1"
        },
        "health": {
            "prescription coverage": "health#2.3",
            "specialist visits": "health#3.4",
            "emergency care": "health#4.1",
            "preventive care": "health#5.2"
        }
    }
    
    for policy in policies_data:
        category = policy["policy_category"]
        for topic in coverage_topics[category]:
            chat = f"""User: Does my policy cover {topic}?
PoliciesAgent: I can check that for you. Could you please let me know your policy number and what type of policy you have (home, auto, etc.)?
User: It's {policy["policy_number"]}, {category} insurance."""
            
            reference = doc_references[category][topic]
            expected = f"Based on our documentation, your {category} policy ({policy['policy_number']}) does include coverage for {topic}. The specific details can be found in our policy documentation (see {reference}). Would you like me to explain more about the coverage limitations or requirements?"
            
            examples.append(PoliciesExample(
                chat_history=chat,
                expected_response=expected,
                policy_number=policy["policy_number"],
                policy_category=category,
                documentation_reference=reference
            ))
    
    # General policy information inquiries
    inquiry_templates = [
        "I need information about my policy coverage.",
        "Can you tell me what my policy covers?",
        "I'd like to know more about my insurance policy.",
        "What does my policy include?",
    ]
    
    for policy in policies_data:
        inquiry = random.choice(inquiry_templates)
        chat = f"""User: {inquiry}
PoliciesAgent: I'd be happy to help. Could you please provide your policy number?
User: {policy["policy_number"]}"""
        
        expected = f"I've checked your {policy['policy_category']} policy ({policy['policy_number']}). Your premium amount is ${policy['premium_amount']} with the next payment due on {policy['due_date']}. Would you like more specific information about your coverage details?"
        
        examples.append(PoliciesExample(
            chat_history=chat,
            expected_response=expected,
            policy_number=policy["policy_number"],
            policy_category=policy["policy_category"]
        ))
    
    return examples


def as_dspy_examples(examples: List[PoliciesExample]) -> List[dspy.Example]:
    """Convert PoliciesExample objects to simplified dspy.Example objects.
    
    For the simplified signature, we only need chat_history and final_response.
    
    Args:
        examples (List[PoliciesExample]): List of policies examples.
        
    Returns:
        List[dspy.Example]: List of dspy.Example objects for the simplified model.
    """
    return [
        dspy.Example(
            chat_history=example.chat_history,
            final_response=example.expected_response
        ).with_inputs("chat_history")
        for example in examples
    ]


if __name__ == "__main__":
    # Generate examples and print them
    examples = create_policies_dataset()
    print(f"Generated {len(examples)} examples")
    
    # Print a sample
    random.seed(42)
    sample = random.sample(examples, min(3, len(examples)))
    for i, example in enumerate(sample):
        print(f"\nExample {i+1}:")
        print(f"Chat history:\n{example.chat_history}")
        print(f"Expected response:\n{example.expected_response}")
        print(f"Policy number: {example.policy_number}")
        print(f"Policy category: {example.policy_category}")
        print(f"Documentation reference: {example.documentation_reference}")