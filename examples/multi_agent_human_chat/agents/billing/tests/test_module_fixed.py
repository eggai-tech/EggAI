"""Fixed test for billing DSPy module that avoids streaming complexity."""

from unittest.mock import MagicMock, patch

import pytest
from dspy import Prediction

from agents.billing.dspy_modules.evaluation.metrics import precision_metric
from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.tests.module")


@pytest.mark.asyncio
async def test_billing_module_without_streaming():
    """Test billing module functionality with proper mocking."""
    # Reset module state
    import agents.billing.dspy_modules.billing as billing_module
    billing_module._initialized = False
    billing_module._billing_model = None
    
    # Mock all the DSPy components
    with patch("agents.billing.dspy_modules.billing.TracedReAct") as mock_traced_react:
        with patch("agents.billing.dspy_modules.billing.dspy.streamify") as mock_streamify:
            with patch("agents.billing.dspy_modules.billing.create_tracer"):
                with patch("agents.billing.dspy_modules.billing.load_optimized_instructions"):
                    
                    # Create a mock model
                    mock_model = MagicMock()
                    mock_model.signature = MagicMock()
                    mock_traced_react.return_value = mock_model
                    
                    # Import after mocking to get mocked version
                    from agents.billing.dspy_modules.billing import (
                        billing_optimized_dspy,
                    )
                    
                    # Create mock response generator
                    async def mock_generator(**kwargs):
                        # Return a simple response
                        response = "Your current amount due is $120.00 with a due date of 2024-02-15. Your status is 'Active'."
                        yield Prediction(final_response=response)
                    
                    # Mock streamify to return our generator
                    mock_streamify.return_value = mock_generator
                    
                    # Test conversation
                    test_history = "User: What's my premium?\nAgent: Please provide your policy number.\nUser: It's B67890."
                    
                    # Run the billing function
                    final_response = None
                    async for chunk in billing_optimized_dspy(test_history):
                        if isinstance(chunk, Prediction) and hasattr(chunk, "final_response"):
                            final_response = chunk.final_response
                            break
                    
                    # Verify we got a response
                    assert final_response is not None
                    assert "amount due" in final_response
                    assert "$120.00" in final_response
                    
                    # Test precision metric
                    expected = "Your current amount due is $120.00 with a due date of 2024-02-15."
                    precision = precision_metric(expected, final_response)
                    assert precision >= 0.7  # Should have decent match
                    
                    logger.info(f"Test passed with response: {final_response[:50]}...")


@pytest.mark.asyncio
async def test_billing_module_error_handling():
    """Test billing module error handling."""
    import agents.billing.dspy_modules.billing as billing_module
    billing_module._initialized = False
    billing_module._billing_model = None
    
    with patch("agents.billing.dspy_modules.billing.TracedReAct") as mock_traced_react:
        with patch("agents.billing.dspy_modules.billing.dspy.streamify") as mock_streamify:
            with patch("agents.billing.dspy_modules.billing.create_tracer"):
                with patch("agents.billing.dspy_modules.billing.load_optimized_instructions"):
                    
                    # Create a mock model
                    mock_model = MagicMock()
                    mock_model.signature = MagicMock()
                    mock_traced_react.return_value = mock_model
                    
                    from agents.billing.dspy_modules.billing import (
                        billing_optimized_dspy,
                    )
                    
                    # Create error generator
                    async def error_generator(**kwargs):
                        raise RuntimeError("Simulated error")
                        yield  # Make it a generator
                    
                    mock_streamify.return_value = error_generator
                    
                    # Test conversation
                    test_history = "User: What's my premium?\nAgent: Please provide your policy number.\nUser: B67890"
                    
                    # Should handle error gracefully
                    with pytest.raises(RuntimeError, match="Simulated error"):
                        async for _chunk in billing_optimized_dspy(test_history):
                            pass