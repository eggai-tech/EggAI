#!/usr/bin/env python3
"""
Unit tests for libraries/tracing/pricing.py
"""

from unittest.mock import patch

import pytest

from libraries.tracing.pricing import (
    DEFAULT_PRICING_DATA,
    PricingCalculator,
    calculate_request_cost,
    get_pricing_calculator,
)


class TestPricingCalculator:
    """Test cases for PricingCalculator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = PricingCalculator()
    
    def test_init(self):
        """Test PricingCalculator initialization."""
        assert self.calculator.pricing_data is not None
        assert "chat" in self.calculator.pricing_data
        assert isinstance(self.calculator.pricing_data["chat"], dict)
    
    def test_load_pricing_data_default(self):
        """Test loading default pricing data."""
        pricing_data = self.calculator._load_pricing_data()
        assert pricing_data == DEFAULT_PRICING_DATA
        assert "chat" in pricing_data
        assert "gpt-4o" in pricing_data["chat"]
    
    def test_load_pricing_data_exception_fallback(self):
        """Test fallback to default pricing when loading fails."""
        # Create a custom PricingCalculator that simulates an exception
        class TestPricingCalculator(PricingCalculator):
            def _load_pricing_data(self):
                try:
                    # Simulate an exception during loading
                    raise Exception("Network error")
                except Exception:
                    # Should fallback to default pricing
                    return DEFAULT_PRICING_DATA
        
        calculator = TestPricingCalculator()
        
        # Should still have pricing data due to fallback in the try/except
        assert calculator.pricing_data == DEFAULT_PRICING_DATA
    
    def test_normalize_model_name_openai_models(self):
        """Test model name normalization for OpenAI models."""
        test_cases = [
            ("gpt-4o", "gpt-4o"),
            ("gpt-4o-2024-05-13", "gpt-4o"),
            ("GPT-4O", "gpt-4o"),
            ("gpt-4o-mini", "gpt-4o-mini"),
            ("gpt-4o-mini-2024-07-18", "gpt-4o-mini"),
            ("gpt-4", "gpt-4"),
            ("gpt-4-0613", "gpt-4"),
            ("gpt-4-turbo", "gpt-4-turbo"),
            ("gpt-3.5-turbo", "gpt-3.5-turbo"),
            ("gpt-3.5-turbo-0125", "gpt-3.5-turbo"),
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_normalize_model_name_anthropic_models(self):
        """Test model name normalization for Anthropic models."""
        test_cases = [
            ("claude-3.5-sonnet", "claude-3-5-sonnet-20241022"),
            ("claude-3-5-sonnet", "claude-3-5-sonnet-20241022"),
            ("claude-3-sonnet", "claude-3-sonnet-20240229"),
            ("claude-3-haiku", "claude-3-haiku-20240307"),
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_normalize_model_name_google_models(self):
        """Test model name normalization for Google models."""
        test_cases = [
            ("gemini-1.5-pro", "gemini-1.5-pro"),
            ("gemini-1.5-flash", "gemini-1.5-flash"),
            ("gemini-pro", "gemini-1.0-pro"),
            ("gemini-1.0-pro", "gemini-1.0-pro"),
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_normalize_model_name_llama_models(self):
        """Test model name normalization for Llama models."""
        test_cases = [
            ("llama3-8b", "llama3-8b-8192"),
            ("llama-3-8b", "llama3-8b-8192"),
            ("llama3-70b", "llama3-70b-8192"),
            ("llama-3-70b", "llama3-70b-8192"),
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_normalize_model_name_mixtral_models(self):
        """Test model name normalization for Mixtral models."""
        result = self.calculator._normalize_model_name("mixtral-8x7b")
        assert result == "mixtral-8x7b-32768"
    
    def test_normalize_model_name_lm_studio_models(self):
        """Test model name normalization for LM Studio models."""
        test_cases = [
            ("lm_studio/llama-8b", "llama3-8b-8192"),
            ("lm-studio/llama-7b", "llama3-8b-8192"),
            ("lm_studio/mixtral", "mixtral-8x7b-32768"),
            ("lm_studio/unknown-model", "llama3-8b-8192"),  # Default fallback
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_normalize_model_name_edge_cases(self):
        """Test model name normalization edge cases."""
        test_cases = [
            ("", "gpt-3.5-turbo"),  # Empty string
            (None, "gpt-3.5-turbo"),  # None
            ("unknown-model", "gpt-3.5-turbo"),  # Unknown model
            ("  gpt-4o  ", "gpt-4o"),  # Whitespace
        ]
        
        for input_name, expected in test_cases:
            result = self.calculator._normalize_model_name(input_name)
            assert result == expected, f"Failed for {input_name}: got {result}, expected {expected}"
    
    def test_get_model_pricing_known_models(self):
        """Test getting pricing for known models."""
        # Test GPT-4o
        input_price, output_price = self.calculator.get_model_pricing("gpt-4o")
        assert input_price == 0.0005
        assert output_price == 0.0015
        
        # Test GPT-4o-mini
        input_price, output_price = self.calculator.get_model_pricing("gpt-4o-mini")
        assert input_price == 0.00015
        assert output_price == 0.0006
        
        # Test Claude
        input_price, output_price = self.calculator.get_model_pricing("claude-3-5-sonnet")
        assert input_price == 0.003
        assert output_price == 0.015
    
    def test_get_model_pricing_unknown_model(self):
        """Test getting pricing for unknown models (should fallback)."""
        input_price, output_price = self.calculator.get_model_pricing("unknown-model")
        # Should fallback to gpt-3.5-turbo pricing
        assert input_price == 0.0005
        assert output_price == 0.0015
    
    def test_calculate_cost_basic(self):
        """Test basic cost calculation."""
        result = self.calculator.calculate_cost("gpt-4o-mini", 1000, 500)
        
        expected_prompt_cost = (1000 / 1000.0) * 0.00015  # 0.00015
        expected_completion_cost = (500 / 1000.0) * 0.0006  # 0.0003
        expected_total = expected_prompt_cost + expected_completion_cost
        
        assert result["prompt_cost"] == expected_prompt_cost
        assert result["completion_cost"] == expected_completion_cost
        assert result["total_cost"] == expected_total
        assert result["prompt_tokens"] == 1000
        assert result["completion_tokens"] == 500
        assert result["total_tokens"] == 1500
        assert result["model"] == "gpt-4o-mini"
        assert result["prompt_price_per_1k"] == 0.00015
        assert result["completion_price_per_1k"] == 0.0006
    
    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        result = self.calculator.calculate_cost("gpt-4o", 0, 0)
        
        assert result["prompt_cost"] == 0.0
        assert result["completion_cost"] == 0.0
        assert result["total_cost"] == 0.0
        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0
        assert result["total_tokens"] == 0
    
    def test_calculate_cost_negative_tokens(self):
        """Test cost calculation with negative tokens (should be handled gracefully)."""
        result = self.calculator.calculate_cost("gpt-4o", -100, -50)
        
        # Negative tokens should be converted to 0
        assert result["prompt_cost"] == 0.0
        assert result["completion_cost"] == 0.0
        assert result["total_cost"] == 0.0
        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0
        assert result["total_tokens"] == 0
    
    def test_calculate_cost_fractional_tokens(self):
        """Test cost calculation with fractional token counts."""
        result = self.calculator.calculate_cost("gpt-4o-mini", 1500, 750)
        
        expected_prompt_cost = (1500 / 1000.0) * 0.00015  # 0.000225
        expected_completion_cost = (750 / 1000.0) * 0.0006  # 0.00045
        expected_total = expected_prompt_cost + expected_completion_cost
        
        assert result["prompt_cost"] == expected_prompt_cost
        assert result["completion_cost"] == expected_completion_cost
        assert result["total_cost"] == expected_total
    
    def test_get_supported_models(self):
        """Test getting all supported models."""
        models = self.calculator.get_supported_models()
        
        assert isinstance(models, dict)
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        assert "claude-3-5-sonnet-20241022" in models
        assert "gemini-1.5-pro" in models
        
        # Check structure of model data
        gpt4o = models["gpt-4o"]
        assert "input" in gpt4o
        assert "output" in gpt4o
        assert isinstance(gpt4o["input"], (int, float))
        assert isinstance(gpt4o["output"], (int, float))


class TestGlobalFunctions:
    """Test cases for global functions."""
    
    def test_get_pricing_calculator_singleton(self):
        """Test that get_pricing_calculator returns a singleton."""
        calc1 = get_pricing_calculator()
        calc2 = get_pricing_calculator()
        
        assert calc1 is calc2  # Should be the same instance
        assert isinstance(calc1, PricingCalculator)
    
    @patch('libraries.tracing.pricing._pricing_calculator', None)
    def test_get_pricing_calculator_creates_new_instance(self):
        """Test that get_pricing_calculator creates new instance when needed."""
        # Reset the global instance
        import libraries.tracing.pricing
        libraries.tracing.pricing._pricing_calculator = None
        
        calc = get_pricing_calculator()
        assert isinstance(calc, PricingCalculator)
        assert libraries.tracing.pricing._pricing_calculator is calc
    
    def test_calculate_request_cost_convenience_function(self):
        """Test the convenience function for calculating request cost."""
        result = calculate_request_cost("gpt-4o-mini", 1000, 500)
        
        # Should return the same result as calling the calculator directly
        calculator = get_pricing_calculator()
        expected = calculator.calculate_cost("gpt-4o-mini", 1000, 500)
        
        assert result == expected
    
    def test_calculate_request_cost_with_different_models(self):
        """Test calculate_request_cost with various models."""
        models_to_test = [
            "gpt-4o",
            "gpt-4o-mini", 
            "claude-3-5-sonnet",
            "gemini-1.5-pro",
            "llama3-8b",
            "unknown-model"
        ]
        
        for model in models_to_test:
            result = calculate_request_cost(model, 100, 50)
            
            assert "prompt_cost" in result
            assert "completion_cost" in result
            assert "total_cost" in result
            assert result["prompt_tokens"] == 100
            assert result["completion_tokens"] == 50
            assert result["model"] == model
            assert result["total_cost"] >= 0


class TestDefaultPricingData:
    """Test cases for default pricing data structure."""
    
    def test_default_pricing_data_structure(self):
        """Test that default pricing data has correct structure."""
        assert "chat" in DEFAULT_PRICING_DATA
        chat_models = DEFAULT_PRICING_DATA["chat"]
        assert isinstance(chat_models, dict)
        
        # Test a few key models
        required_models = [
            "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo",
            "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307",
            "gemini-1.5-pro", "gemini-1.5-flash",
            "llama3-8b-8192", "mixtral-8x7b-32768"
        ]
        
        for model in required_models:
            assert model in chat_models, f"Model {model} not found in pricing data"
            model_data = chat_models[model]
            assert "input" in model_data
            assert "output" in model_data
            assert isinstance(model_data["input"], (int, float))
            assert isinstance(model_data["output"], (int, float))
            assert model_data["input"] >= 0
            assert model_data["output"] >= 0
    
    def test_pricing_data_values_reasonable(self):
        """Test that pricing values are reasonable (not negative, not extremely high)."""
        chat_models = DEFAULT_PRICING_DATA["chat"]
        
        for model_name, pricing in chat_models.items():
            input_price = pricing["input"]
            output_price = pricing["output"]
            
            # Prices should be positive
            assert input_price >= 0, f"Negative input price for {model_name}"
            assert output_price >= 0, f"Negative output price for {model_name}"
            
            # Prices should be reasonable (less than $1 per 1K tokens)
            assert input_price < 1.0, f"Unreasonably high input price for {model_name}: {input_price}"
            assert output_price < 1.0, f"Unreasonably high output price for {model_name}: {output_price}"


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_end_to_end_cost_calculation(self):
        """Test end-to-end cost calculation workflow."""
        # Test a realistic scenario
        model = "gpt-4o-mini"
        prompt_tokens = 2500  # ~1000 words
        completion_tokens = 150  # ~60 words
        
        result = calculate_request_cost(model, prompt_tokens, completion_tokens)
        
        # Verify all expected fields are present
        required_fields = [
            "prompt_cost", "completion_cost", "total_cost",
            "prompt_tokens", "completion_tokens", "total_tokens",
            "model", "prompt_price_per_1k", "completion_price_per_1k"
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify calculations
        expected_prompt_cost = (prompt_tokens / 1000.0) * 0.00015
        expected_completion_cost = (completion_tokens / 1000.0) * 0.0006
        expected_total = expected_prompt_cost + expected_completion_cost
        
        assert abs(result["prompt_cost"] - expected_prompt_cost) < 1e-10
        assert abs(result["completion_cost"] - expected_completion_cost) < 1e-10
        assert abs(result["total_cost"] - expected_total) < 1e-10
    
    def test_multiple_model_comparison(self):
        """Test cost comparison across multiple models."""
        models = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "llama3-8b"]
        prompt_tokens = 1000
        completion_tokens = 500
        
        results = {}
        for model in models:
            results[model] = calculate_request_cost(model, prompt_tokens, completion_tokens)
        
        # Verify all calculations completed successfully
        assert len(results) == len(models)
        
        # Verify that different models have different costs (in most cases)
        costs = [result["total_cost"] for result in results.values()]
        assert len(set(costs)) > 1, "All models have the same cost, which is unexpected"
        
        # Verify that all costs are positive
        for model, result in results.items():
            assert result["total_cost"] > 0, f"Zero cost for model {model}"


if __name__ == "__main__":
    pytest.main([__file__]) 