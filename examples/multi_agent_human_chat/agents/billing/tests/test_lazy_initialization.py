"""Tests for lazy initialization and new code in billing module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from agents.billing.dspy_modules.billing import (
    _initialize_billing_model,
    load_optimized_instructions,
)


class TestLazyInitialization:
    """Test the lazy initialization of billing model."""

    def test_load_optimized_instructions_file_not_exists(self):
        """Test load_optimized_instructions when file doesn't exist."""
        fake_path = Path("/non/existent/path.json")
        result = load_optimized_instructions(fake_path)
        assert result is None

    def test_load_optimized_instructions_valid_file(self):
        """Test load_optimized_instructions with valid JSON file."""
        valid_json = {
            "react": {
                "signature": {
                    "instructions": "Test optimized instructions"
                }
            }
        }
        
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        # Create a proper context manager mock
        mock_file = mock_open(read_data=json.dumps(valid_json))()
        mock_path.open.return_value = mock_file
        
        result = load_optimized_instructions(mock_path)
        assert result == "Test optimized instructions"

    def test_load_optimized_instructions_invalid_structure(self):
        """Test load_optimized_instructions with invalid JSON structure."""
        invalid_json = {"wrong": "structure"}
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(invalid_json))):
                result = load_optimized_instructions(Path("test.json"))
                assert result is None

    def test_load_optimized_instructions_no_instructions(self):
        """Test load_optimized_instructions when instructions field is missing."""
        json_no_instructions = {
            "react": {
                "signature": {
                    "other_field": "value"
                }
            }
        }
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(json_no_instructions))):
                result = load_optimized_instructions(Path("test.json"))
                assert result is None

    def test_load_optimized_instructions_json_decode_error(self):
        """Test load_optimized_instructions with invalid JSON."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json")):
                with patch("agents.billing.dspy_modules.billing.logger") as mock_logger:
                    result = load_optimized_instructions(Path("test.json"))
                    assert result is None
                    mock_logger.error.assert_called_once()

    @patch("agents.billing.dspy_modules.billing._initialized", False)
    @patch("agents.billing.dspy_modules.billing._billing_model", None)
    def test_initialize_billing_model_first_time(self):
        """Test _initialize_billing_model when not initialized."""
        with patch("agents.billing.dspy_modules.billing.create_tracer") as mock_tracer:
            with patch("agents.billing.dspy_modules.billing.load_optimized_instructions") as mock_load:
                with patch("agents.billing.dspy_modules.billing.TracedReAct") as mock_traced_react:
                    mock_load.return_value = None
                    mock_model = MagicMock()
                    mock_traced_react.return_value = mock_model
                    
                    # Reset the module-level variables
                    import agents.billing.dspy_modules.billing as billing_module
                    billing_module._initialized = False
                    billing_module._billing_model = None
                    
                    result = _initialize_billing_model()
                    
                    assert result == mock_model
                    mock_tracer.assert_called_once_with("billing_agent")
                    mock_traced_react.assert_called_once()
                    assert billing_module._initialized is True

    @patch("agents.billing.dspy_modules.billing._initialized", True)
    def test_initialize_billing_model_already_initialized(self):
        """Test _initialize_billing_model when already initialized."""
        # Set up a mock model
        mock_model = MagicMock()
        
        import agents.billing.dspy_modules.billing as billing_module
        billing_module._initialized = True
        billing_module._billing_model = mock_model
        
        with patch("agents.billing.dspy_modules.billing.create_tracer") as mock_tracer:
            result = _initialize_billing_model()
            
            assert result == mock_model
            mock_tracer.assert_not_called()  # Should not create tracer again

    def test_initialize_billing_model_with_optimized_instructions(self):
        """Test _initialize_billing_model with optimized instructions."""
        with patch("agents.billing.dspy_modules.billing.create_tracer"):
            with patch("agents.billing.dspy_modules.billing.load_optimized_instructions") as mock_load:
                with patch("agents.billing.dspy_modules.billing.TracedReAct"):
                    with patch("agents.billing.dspy_modules.billing.BillingSignature") as mock_signature:
                        mock_load.return_value = "Optimized instructions"
                        
                        # Reset the module-level variables
                        import agents.billing.dspy_modules.billing as billing_module
                        billing_module._initialized = False
                        billing_module._billing_model = None
                        
                        _initialize_billing_model()
                        
                        # Check that the signature's __doc__ was updated
                        assert mock_signature.__doc__ == "Optimized instructions"
                        assert billing_module._initialized is True


class TestBillingModelFunctionality:
    """Test billing model functionality and edge cases."""

    def test_truncate_long_history_boundary(self):
        """Test truncate_long_history at exact boundary."""
        from agents.billing.dspy_modules.billing import (
            ModelConfig,
            truncate_long_history,
        )
        
        config = ModelConfig(truncation_length=1000)
        history = "x" * 1000  # Exactly at limit
        
        result = truncate_long_history(history, config)
        assert result["history"] == history
        assert result["truncated"] is False
        assert result["original_length"] == 1000
        assert result["truncated_length"] == 1000

    def test_truncate_long_history_just_over_limit(self):
        """Test truncate_long_history just over the limit."""
        from agents.billing.dspy_modules.billing import (
            ModelConfig,
            truncate_long_history,
        )
        
        config = ModelConfig(truncation_length=1000)
        # Create history with many lines
        lines = ["Line " + str(i) for i in range(50)]
        history = "\n".join(lines)
        # Make it exceed the length limit
        history = history + "x" * 900  # This will make it exceed 1000 chars
        
        result = truncate_long_history(history, config)
        assert result["truncated"] is True
        assert result["original_length"] > 1000
        # Should keep last 30 lines
        assert result["history"].count("\n") <= 30

    @pytest.mark.asyncio
    async def test_billing_optimized_dspy_with_config(self):
        """Test billing_optimized_dspy with custom config."""
        from dspy import Prediction

        from agents.billing.dspy_modules.billing import (
            ModelConfig,
            billing_optimized_dspy,
        )
        
        config = ModelConfig(truncation_length=1000)
        history = "User: Test\nAgent: Response"
        
        # Mock the dependencies
        with patch("agents.billing.dspy_modules.billing._initialize_billing_model") as mock_init:
            with patch("agents.billing.dspy_modules.billing.dspy.streamify") as mock_streamify:
                # Create a mock async generator
                async def mock_generator(**kwargs):
                    yield Prediction(final_response="Test response")
                
                mock_streamify.return_value = mock_generator
                mock_init.return_value = MagicMock()
                
                chunks = []
                async for chunk in billing_optimized_dspy(history, config):
                    chunks.append(chunk)
                
                assert len(chunks) == 1
                assert isinstance(chunks[0], Prediction)
                assert chunks[0].final_response == "Test response"