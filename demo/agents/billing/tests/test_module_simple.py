from unittest.mock import MagicMock, patch


class TestBillingModule:
    """Test basic billing module functionality."""

    def test_truncate_long_history_under_limit(self):
        """Test truncation when history is under the limit."""
        from agents.billing.dspy_modules.billing import truncate_long_history
        from agents.billing.types import ModelConfig
        
        config = ModelConfig(truncation_length=1000)
        history = "Short history"
        
        result = truncate_long_history(history, config)
        
        assert result["history"] == history
        assert result["truncated"] is False
        assert result["original_length"] == len(history)
        assert result["truncated_length"] == len(history)

    def test_truncate_long_history_over_limit(self):
        """Test truncation when history exceeds the limit."""
        from agents.billing.dspy_modules.billing import truncate_long_history
        from agents.billing.types import ModelConfig
        
        config = ModelConfig(truncation_length=1000)
        # Create history that exceeds limit
        lines = [f"Line {i}: This is a test line that is quite long to make sure we exceed the limit" for i in range(100)]
        history = "\n".join(lines)
        
        result = truncate_long_history(history, config)
        
        assert result["truncated"] is True
        # The truncation keeps last 30 lines, which might exceed the truncation_length
        # Just verify it's actually truncated
        assert len(result["history"]) < len(history)
        assert result["history"].count("\n") <= 30  # Should keep last 30 lines
        assert result["original_length"] == len(history)
        assert result["truncated_length"] == len(result["history"])

    @patch("agents.billing.dspy_modules.billing.TracedReAct")
    @patch("agents.billing.dspy_modules.billing.create_tracer")
    @patch("agents.billing.dspy_modules.billing.load_optimized_instructions")
    def test_initialize_billing_model(self, mock_load, mock_tracer, mock_traced_react):
        """Test billing model initialization."""
        # Reset module state
        import agents.billing.dspy_modules.billing as billing_module
        from agents.billing.dspy_modules.billing import _initialize_billing_model
        billing_module._initialized = False
        billing_module._billing_model = None
        
        # Mock setup
        mock_load.return_value = None
        mock_model = MagicMock()
        mock_traced_react.return_value = mock_model
        
        # Initialize model
        result = _initialize_billing_model()
        
        # Verify initialization
        assert result == mock_model
        assert billing_module._initialized is True
        assert billing_module._billing_model == mock_model
        mock_tracer.assert_called_once_with("billing_agent")
        mock_traced_react.assert_called_once()

    @patch("agents.billing.dspy_modules.billing.TracedReAct")
    @patch("agents.billing.dspy_modules.billing.create_tracer") 
    @patch("agents.billing.dspy_modules.billing.load_optimized_instructions")
    def test_initialize_billing_model_with_optimized(self, mock_load, mock_tracer, mock_traced_react):
        """Test billing model initialization with optimized instructions."""
        # Reset module state
        import agents.billing.dspy_modules.billing as billing_module
        from agents.billing.dspy_modules.billing import (
            BillingSignature,
            _initialize_billing_model,
        )
        billing_module._initialized = False
        billing_module._billing_model = None
        
        # Mock setup with optimized instructions
        optimized_instructions = "Optimized billing instructions"
        mock_load.return_value = optimized_instructions
        mock_model = MagicMock()
        mock_traced_react.return_value = mock_model
        
        # Initialize model
        result = _initialize_billing_model()
        
        # Verify optimized instructions were applied
        assert BillingSignature.__doc__ == optimized_instructions
        assert result == mock_model

    def test_model_config_defaults(self):
        """Test ModelConfig default values."""
        from agents.billing.types import ModelConfig
        
        config = ModelConfig()
        
        assert config.name == "billing_react"
        assert config.max_iterations == 5
        assert config.use_tracing is True
        assert config.cache_enabled is False
        assert config.truncation_length == 15000
        assert config.timeout_seconds == 30.0

    def test_model_config_custom_values(self):
        """Test ModelConfig with custom values."""
        from agents.billing.types import ModelConfig
        
        config = ModelConfig(
            name="custom_billing",
            timeout_seconds=60.0,
            truncation_length=20000
        )
        
        assert config.name == "custom_billing"
        assert config.timeout_seconds == 60.0
        assert config.truncation_length == 20000
        # Other values should still be defaults
        assert config.max_iterations == 5
        assert config.use_tracing is True