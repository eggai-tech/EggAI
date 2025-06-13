"""Tests for claims dataset module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import dspy

from agents.claims.dspy_modules.claims_dataset import (
    ClaimsExample,
    as_dspy_examples,
    create_claims_dataset,
    export_dataset,
    load_dataset,
)


def test_claims_example_dataclass():
    """Test ClaimsExample dataclass structure."""
    example = ClaimsExample(
        chat_history="User: Hello",
        expected_response="Hello! How can I help?"
    )
    
    assert example.chat_history == "User: Hello"
    assert example.expected_response == "Hello! How can I help?"


def test_create_claims_dataset():
    """Test creating claims dataset."""
    dataset = create_claims_dataset()
    
    # Should have examples
    assert len(dataset) > 0
    
    # All items should be ClaimsExample instances
    for example in dataset:
        assert isinstance(example, ClaimsExample)
        assert hasattr(example, 'chat_history')
        assert hasattr(example, 'expected_response')
        assert isinstance(example.chat_history, str)
        assert isinstance(example.expected_response, str)
        assert len(example.chat_history) > 0
        assert len(example.expected_response) > 0


def test_dataset_contains_status_inquiries():
    """Test that dataset contains claim status inquiry examples."""
    dataset = create_claims_dataset()
    
    status_examples = [
        ex for ex in dataset 
        if 'check my claim status' in ex.chat_history.lower() or 'claim status' in ex.chat_history.lower()
    ]
    
    assert len(status_examples) > 0
    
    # Check that status examples have proper structure
    for example in status_examples:
        assert 'claim number' in example.chat_history.lower()
        assert any(status in example.expected_response.lower() 
                  for status in ['in review', 'approved', 'pending'])


def test_dataset_contains_filing_examples():
    """Test that dataset contains claim filing examples."""
    dataset = create_claims_dataset()
    
    filing_examples = [
        ex for ex in dataset 
        if 'file a new claim' in ex.chat_history.lower() or 'new claim' in ex.chat_history.lower()
    ]
    
    assert len(filing_examples) > 0
    
    # Check that filing examples have proper structure
    for example in filing_examples:
        assert 'policy number' in example.chat_history.lower()
        assert any(incident in example.chat_history.lower() 
                  for incident in ['accident', 'damage', 'stolen', 'hurricane', 'vandalism'])
        assert 'filed a new claim' in example.expected_response.lower()


def test_dataset_contains_update_examples():
    """Test that dataset contains claim update examples."""
    dataset = create_claims_dataset()
    
    update_examples = [
        ex for ex in dataset 
        if 'update information' in ex.chat_history.lower() or 'change the' in ex.chat_history.lower()
    ]
    
    assert len(update_examples) > 0
    
    # Check that update examples have proper structure
    for example in update_examples:
        assert 'claim number' in example.chat_history.lower()
        assert any(field in example.chat_history.lower() 
                  for field in ['address', 'phone', 'damage', 'date'])


def test_dataset_example_types():
    """Test that dataset contains different types of claims inquiries."""
    dataset = create_claims_dataset()
    
    # Check for different inquiry types
    inquiry_types = {
        'status_check': False,
        'file_claim': False,
        'update_info': False
    }
    
    for example in dataset:
        chat_lower = example.chat_history.lower()
        if 'status' in chat_lower or 'check' in chat_lower:
            inquiry_types['status_check'] = True
        if 'file' in chat_lower or 'new claim' in chat_lower:
            inquiry_types['file_claim'] = True
        if 'update' in chat_lower or 'change' in chat_lower:
            inquiry_types['update_info'] = True
    
    # Should have at least some variety
    assert sum(inquiry_types.values()) >= 2


def test_as_dspy_examples():
    """Test converting ClaimsExample to dspy.Example."""
    claims_examples = [
        ClaimsExample(
            chat_history="User: What's my claim status?",
            expected_response="Please provide your claim number."
        ),
        ClaimsExample(
            chat_history="User: I need to file a claim.",
            expected_response="I can help you file a claim."
        )
    ]
    
    dspy_examples = as_dspy_examples(claims_examples)
    
    assert len(dspy_examples) == 2
    
    for i, dspy_ex in enumerate(dspy_examples):
        assert isinstance(dspy_ex, dspy.Example)
        assert dspy_ex.chat_history == claims_examples[i].chat_history
        assert dspy_ex.final_response == claims_examples[i].expected_response
        # Check that inputs are set correctly
        assert 'chat_history' in dspy_ex._input_keys


def test_as_dspy_examples_empty_list():
    """Test converting empty list to dspy examples."""
    dspy_examples = as_dspy_examples([])
    
    assert len(dspy_examples) == 0
    assert isinstance(dspy_examples, list)


def test_export_dataset():
    """Test exporting dataset to JSON file."""
    examples = [
        ClaimsExample(
            chat_history="User: Test chat",
            expected_response="Test response"
        ),
        ClaimsExample(
            chat_history="User: Another test",
            expected_response="Another response"
        )
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        export_dataset(examples, tmp_path)
        
        # Verify file was created and contains correct data
        assert os.path.exists(tmp_path)
        
        with open(tmp_path, 'r') as f:
            data = json.load(f)
        
        assert len(data) == 2
        assert data[0]['chat_history'] == "User: Test chat"
        assert data[0]['expected_response'] == "Test response"
        assert data[1]['chat_history'] == "User: Another test"
        assert data[1]['expected_response'] == "Another response"
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_export_dataset_default_path():
    """Test exporting dataset with default path."""
    examples = [
        ClaimsExample(
            chat_history="User: Test",
            expected_response="Response"
        )
    ]
    
    # Mock the default path to avoid creating files in the actual module directory
    expected_path = Path(__file__).resolve().parent.parent / "dspy_modules" / "claims_dataset.json"
    
    with patch('builtins.open', create=True) as mock_open:
        with patch('json.dump') as mock_json_dump:
            export_dataset(examples)
            
            # Verify open was called with expected path
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0]
            assert str(expected_path) in str(call_args[0])
            
            # Verify json.dump was called
            mock_json_dump.assert_called_once()


def test_export_dataset_error_handling():
    """Test export dataset error handling."""
    examples = [
        ClaimsExample(
            chat_history="User: Test",
            expected_response="Response"
        )
    ]
    
    # Use an invalid path to trigger an error
    invalid_path = "/invalid/path/that/does/not/exist/file.json"
    
    # Should not raise exception, but should log error
    export_dataset(examples, invalid_path)


def test_load_dataset():
    """Test loading dataset from JSON file."""
    # Create test data
    test_data = [
        {
            "chat_history": "User: Load test",
            "expected_response": "Loaded response"
        },
        {
            "chat_history": "User: Another load test",
            "expected_response": "Another loaded response"
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(test_data, tmp_file)
        tmp_path = tmp_file.name
    
    try:
        examples = load_dataset(tmp_path)
        
        assert len(examples) == 2
        assert isinstance(examples[0], ClaimsExample)
        assert examples[0].chat_history == "User: Load test"
        assert examples[0].expected_response == "Loaded response"
        assert examples[1].chat_history == "User: Another load test"
        assert examples[1].expected_response == "Another loaded response"
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_load_dataset_file_not_found():
    """Test loading dataset when file doesn't exist."""
    non_existent_path = "/path/that/does/not/exist.json"
    
    # Should fall back to creating new dataset
    examples = load_dataset(non_existent_path)
    
    assert len(examples) > 0
    assert all(isinstance(ex, ClaimsExample) for ex in examples)


def test_load_dataset_default_path():
    """Test loading dataset with default path when file doesn't exist."""
    # Mock the default path to a non-existent file
    with patch('os.path.exists', return_value=False):
        with patch('agents.claims.dspy_modules.claims_dataset.create_claims_dataset') as mock_create:
            mock_create.return_value = [
                ClaimsExample(
                    chat_history="Mock chat",
                    expected_response="Mock response"
                )
            ]
            
            examples = load_dataset()
            
            # Should have called create_claims_dataset as fallback
            mock_create.assert_called_once()
            assert len(examples) == 1


def test_load_dataset_invalid_json():
    """Test loading dataset with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_file.write("invalid json content")
        tmp_path = tmp_file.name
    
    try:
        # Should fall back to creating new dataset
        examples = load_dataset(tmp_path)
        
        assert len(examples) > 0
        assert all(isinstance(ex, ClaimsExample) for ex in examples)
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_dataset_claim_numbers():
    """Test that dataset uses expected claim numbers."""
    dataset = create_claims_dataset()
    
    # Should contain references to known claim numbers
    claim_numbers = ["1001", "1002", "1003"]
    
    for claim_num in claim_numbers:
        examples_with_claim = [
            ex for ex in dataset 
            if claim_num in ex.chat_history or claim_num in ex.expected_response
        ]
        assert len(examples_with_claim) > 0


def test_dataset_policy_numbers():
    """Test that dataset uses expected policy numbers."""
    dataset = create_claims_dataset()
    
    # Should contain references to known policy numbers
    policy_numbers = ["A12345", "B67890", "C24680"]
    
    for policy_num in policy_numbers:
        examples_with_policy = [
            ex for ex in dataset 
            if policy_num in ex.chat_history or policy_num in ex.expected_response
        ]
        assert len(examples_with_policy) > 0


def test_dataset_incident_types():
    """Test that dataset includes various incident types."""
    dataset = create_claims_dataset()
    
    incident_types = ["accident", "damage", "stolen", "hurricane", "vandalism"]
    
    found_incidents = set()
    for example in dataset:
        for incident in incident_types:
            if incident in example.chat_history.lower():
                found_incidents.add(incident)
    
    # Should have at least some incident types
    assert len(found_incidents) > 0


def test_dataset_conversation_structure():
    """Test that dataset examples have proper conversation structure."""
    dataset = create_claims_dataset()
    
    for example in dataset:
        # Should have User and ClaimsAgent in chat history
        assert "User:" in example.chat_history
        assert "ClaimsAgent:" in example.chat_history
        
        # Expected response should be non-empty
        assert len(example.expected_response.strip()) > 0


def test_dataset_randomization():
    """Test that dataset includes randomized elements."""
    # Create dataset multiple times to check for randomization
    dataset1 = create_claims_dataset()
    dataset2 = create_claims_dataset()
    
    # Should have same length (deterministic structure)
    assert len(dataset1) == len(dataset2)
    
    # But some examples might be different due to random sampling
    # (This test mainly ensures the random.sample calls work)
    assert all(isinstance(ex, ClaimsExample) for ex in dataset1)
    assert all(isinstance(ex, ClaimsExample) for ex in dataset2)


def test_dataset_field_updates():
    """Test that dataset includes field update examples."""
    dataset = create_claims_dataset()
    
    update_fields = ["address", "phone", "damage_description", "incident date"]
    
    found_fields = set()
    for example in dataset:
        for field in update_fields:
            if field in example.chat_history.lower():
                found_fields.add(field)
    
    # Should have examples for updating different fields
    assert len(found_fields) > 0


def test_dataset_follow_up_examples():
    """Test that dataset includes follow-up conversation examples."""
    dataset = create_claims_dataset()
    
    # Look for examples that have multiple exchanges
    multi_exchange_examples = [
        ex for ex in dataset 
        if ex.chat_history.count("User:") > 1 and ex.chat_history.count("ClaimsAgent:") > 1
    ]
    
    assert len(multi_exchange_examples) > 0
    
    # Check that follow-up examples have proper structure
    for example in multi_exchange_examples:
        lines = example.chat_history.split('\n')
        user_lines = [line for line in lines if line.startswith("User:")]
        agent_lines = [line for line in lines if line.startswith("ClaimsAgent:")]
        
        # Should have multiple exchanges
        assert len(user_lines) > 1
        assert len(agent_lines) > 1


def test_export_load_roundtrip():
    """Test that export and load work together correctly."""
    original_examples = [
        ClaimsExample(
            chat_history="User: Roundtrip test",
            expected_response="Roundtrip response"
        ),
        ClaimsExample(
            chat_history="User: Another roundtrip",
            expected_response="Another roundtrip response"
        )
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        # Export then load
        export_dataset(original_examples, tmp_path)
        loaded_examples = load_dataset(tmp_path)
        
        # Should be identical
        assert len(loaded_examples) == len(original_examples)
        for orig, loaded in zip(original_examples, loaded_examples, strict=False):
            assert orig.chat_history == loaded.chat_history
            assert orig.expected_response == loaded.expected_response
            
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path) 