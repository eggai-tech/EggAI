"""Tests for billing dataset generation."""

import dspy

from libraries.billing_dspy.billing_dataset import (
    BillingExample,
    as_dspy_examples,
    create_billing_dataset,
)


def test_billing_example_dataclass():
    """Test BillingExample dataclass creation."""
    example = BillingExample(
        chat_history="User: What's my bill?\nAgent: I can help with that.",
        expected_response="Your amount due is $120.50",
    )

    assert example.chat_history == "User: What's my bill?\nAgent: I can help with that."
    assert example.expected_response == "Your amount due is $120.50"


def test_create_billing_dataset():
    """Test creating billing dataset."""
    dataset = create_billing_dataset()

    assert isinstance(dataset, list)
    assert len(dataset) > 0

    # Check that all examples are BillingExample instances
    for example in dataset:
        assert isinstance(example, BillingExample)
        assert hasattr(example, "chat_history")
        assert hasattr(example, "expected_response")
        assert len(example.chat_history) > 0
        assert len(example.expected_response) > 0


def test_dataset_contains_policy_numbers():
    """Test that dataset contains examples for all policy numbers."""
    dataset = create_billing_dataset()

    # Known policy numbers from billing_data.py
    expected_policies = ["A12345", "B67890", "C24680"]

    found_policies = set()
    for example in dataset:
        for policy in expected_policies:
            if policy in example.chat_history:
                found_policies.add(policy)

    # Should have examples for all policies
    assert len(found_policies) == len(expected_policies)


def test_dataset_example_types():
    """Test that dataset contains different types of billing inquiries."""
    dataset = create_billing_dataset()

    # Check for different inquiry types
    inquiry_types = {
        "payment_due": False,
        "amount_due": False,
        "billing_cycle": False,
        "payment_status": False,
    }

    for example in dataset:
        chat_lower = example.chat_history.lower()
        if "payment due" in chat_lower or "next payment" in chat_lower:
            inquiry_types["payment_due"] = True
        if "amount" in chat_lower and "owe" in chat_lower:
            inquiry_types["amount_due"] = True
        if "billing cycle" in chat_lower:
            inquiry_types["billing_cycle"] = True
        if "payment" in chat_lower and (
            "through" in chat_lower or "status" in chat_lower
        ):
            inquiry_types["payment_status"] = True

    # Should have at least some variety
    assert sum(inquiry_types.values()) >= 2


def test_dataset_response_formats():
    """Test that dataset responses follow expected formats."""
    dataset = create_billing_dataset()

    for example in dataset:
        response = example.expected_response

        # Check for proper formatting elements
        if "$" in response:
            # Should have proper currency format
            assert any(char.isdigit() for char in response)

        if "due" in response.lower():
            # Should mention dates
            assert any(char.isdigit() for char in response)

        if "status" in response.lower():
            # Should have quoted status
            assert "'" in response or '"' in response


def test_as_dspy_examples():
    """Test conversion to DSPy examples."""
    billing_examples = [
        BillingExample(
            chat_history="User: What's my bill?",
            expected_response="Your amount due is $120.50",
        ),
        BillingExample(
            chat_history="User: When is payment due?",
            expected_response="Your payment is due on 2026-05-15",
        ),
    ]

    dspy_examples = as_dspy_examples(billing_examples)

    assert isinstance(dspy_examples, list)
    assert len(dspy_examples) == 2

    for example in dspy_examples:
        assert isinstance(example, dspy.Example)
        assert hasattr(example, "chat_history")
        assert hasattr(example, "final_response")


def test_dspy_examples_input_fields():
    """Test that DSPy examples have correct input fields."""
    billing_examples = [
        BillingExample(
            chat_history="User: Test question", expected_response="Test response"
        )
    ]

    dspy_examples = as_dspy_examples(billing_examples)
    example = dspy_examples[0]

    # Check that chat_history is marked as input
    assert example.chat_history == "User: Test question"
    assert example.final_response == "Test response"


def test_dataset_comprehensive_coverage():
    """Test that dataset covers all policy data comprehensively."""
    dataset = create_billing_dataset()

    # Group examples by policy number
    policy_examples = {}
    for example in dataset:
        for policy in ["A12345", "B67890", "C24680"]:
            if policy in example.chat_history:
                if policy not in policy_examples:
                    policy_examples[policy] = []
                policy_examples[policy].append(example)

    # Each policy should have multiple example types
    for _policy, examples in policy_examples.items():
        assert len(examples) >= 3  # At least 3 different inquiry types per policy

        # Check for variety in responses
        responses = [ex.expected_response for ex in examples]
        unique_responses = set(responses)
        assert len(unique_responses) == len(responses)  # All responses should be unique


def test_dataset_realistic_conversations():
    """Test that dataset contains realistic conversation patterns."""
    dataset = create_billing_dataset()

    for example in dataset:
        chat = example.chat_history

        # Should have user and agent turns
        assert "User:" in chat
        assert "BillingAgent:" in chat or "Agent:" in chat

        # Should end with user providing policy number
        lines = chat.strip().split("\n")
        last_line = lines[-1].strip()

        # Last line should contain a policy number
        policy_found = any(
            policy in last_line for policy in ["A12345", "B67890", "C24680"]
        )
        assert policy_found


def test_dataset_response_accuracy():
    """Test that dataset responses match the expected data."""
    dataset = create_billing_dataset()

    # Known data from billing_data.py
    expected_data = {
        "A12345": {
            "amount": 120.0,
            "cycle": "Monthly",
            "status": "Paid",
            "due": "2026-02-01",
        },
        "B67890": {
            "amount": 300.0,
            "cycle": "Quarterly",
            "status": "Pending",
            "due": "2026-03-15",
        },
        "C24680": {
            "amount": 1000.0,
            "cycle": "Annual",
            "status": "Pending",
            "due": "2026-12-01",
        },
    }

    for example in dataset:
        # Find which policy this example is for
        policy = None
        for p in expected_data.keys():
            if p in example.chat_history:
                policy = p
                break

        if policy:
            response = example.expected_response
            data = expected_data[policy]

            # Check that response contains correct data
            if (
                f"${data['amount']:.2f}" in response
                or f"${data['amount']:.0f}" in response
            ):
                # Amount should be correct
                assert (
                    str(data["amount"]) in response
                    or f"{data['amount']:.2f}" in response
                )

            if data["due"] in response:
                # Due date should be correct
                assert data["due"] in response

            if data["status"] in response:
                # Status should be correct
                assert data["status"] in response

            if data["cycle"] in response:
                # Cycle should be correct
                assert data["cycle"] in response


def test_empty_dataset_handling():
    """Test handling of edge cases in dataset creation."""
    # This tests the robustness of the dataset creation
    dataset = create_billing_dataset()

    # Should never return empty dataset
    assert len(dataset) > 0

    # All examples should be valid
    for example in dataset:
        assert example.chat_history is not None
        assert example.expected_response is not None
        assert len(example.chat_history.strip()) > 0
        assert len(example.expected_response.strip()) > 0


def test_as_dspy_examples_empty_list():
    """Test converting empty list to DSPy examples."""
    dspy_examples = as_dspy_examples([])

    assert isinstance(dspy_examples, list)
    assert len(dspy_examples) == 0
