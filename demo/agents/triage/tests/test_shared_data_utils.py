"""Tests for shared data utilities."""

import pytest

from agents.triage.shared.data_utils import create_examples


class TestSharedDataUtils:
    """Test shared data utility functions."""

    def test_create_training_examples_basic(self):
        """Test basic functionality of create_examples."""
        examples = create_examples(sample_size=5, seed=42)
        assert len(examples) == 5
        
        for example in examples:
            assert hasattr(example, 'chat_history')
            assert hasattr(example, 'target_agent')
            assert isinstance(example.chat_history, str)
            assert isinstance(example.target_agent, str)

    def test_create_training_examples_deterministic(self):
        """Test deterministic sampling with seed."""
        examples_1 = create_examples(sample_size=5, seed=42)
        examples_2 = create_examples(sample_size=5, seed=42)
        
        assert len(examples_1) == 5
        assert len(examples_2) == 5
        
        # Should be identical with same seed
        for ex1, ex2 in zip(examples_1, examples_2, strict=False):
            assert ex1.chat_history == ex2.chat_history
            assert ex1.target_agent == ex2.target_agent

    def test_create_training_examples_different_seeds(self):
        """Test different seeds produce different results."""
        examples_1 = create_examples(sample_size=5, seed=42)
        examples_2 = create_examples(sample_size=5, seed=999)
        
        assert len(examples_1) == 5
        assert len(examples_2) == 5
        
        # Should be different with different seeds (high probability)
        different_count = sum(1 for ex1, ex2 in zip(examples_1, examples_2, strict=False) 
                             if ex1.chat_history != ex2.chat_history)
        assert different_count > 0

    def test_create_training_examples_all_data(self):
        """Test getting all available data."""
        examples_all = create_examples(sample_size=-1)
        assert len(examples_all) > 0
        
        # Should be larger than small samples
        examples_small = create_examples(sample_size=5)
        assert len(examples_all) > len(examples_small)

    def test_create_training_examples_oversample(self):
        """Test requesting more samples than available."""
        examples_all = create_examples(sample_size=-1)
        total_available = len(examples_all)
        
        # Request more than available
        examples_over = create_examples(sample_size=total_available + 1000)
        
        # Should return all available data
        assert len(examples_over) == total_available

    def test_create_training_examples_edge_cases(self):
        """Test edge cases for sample sizes."""
        # Zero samples
        examples_zero = create_examples(sample_size=0)
        assert len(examples_zero) == 0
        
        # Single sample
        examples_one = create_examples(sample_size=1, seed=42)
        assert len(examples_one) == 1

    def test_create_training_examples_consistent_format(self):
        """Test that all examples have consistent format."""
        examples = create_examples(sample_size=10, seed=42)
        
        valid_agents = {'BillingAgent', 'ClaimsAgent', 'PolicyAgent', 'EscalationAgent', 'ChattyAgent'}
        
        for example in examples:
            # Check required attributes exist
            assert hasattr(example, 'chat_history')
            assert hasattr(example, 'target_agent')
            
            # Check types
            assert isinstance(example.chat_history, str)
            assert isinstance(example.target_agent, str)
            
            # Check chat_history is not empty
            assert len(example.chat_history.strip()) > 0
            
            # Check target_agent is valid
            assert example.target_agent in valid_agents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])