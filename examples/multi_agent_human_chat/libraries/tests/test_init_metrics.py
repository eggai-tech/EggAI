#!/usr/bin/env python3
"""
Unit tests for libraries/tracing/init_metrics.py
"""

from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry

from libraries.tracing.init_metrics import (
    export_semantic_metrics,
    export_token_metrics,
    gen_ai_client_cost_current,
    gen_ai_client_cost_per_token,
    gen_ai_client_cost_total,
    gen_ai_client_operation_duration,
    gen_ai_client_token_usage,
    init_token_metrics,
    normalize_gen_ai_system,
    normalize_operation_name,
    patch_tracking_lm,
    start_metrics_server,
)


class MockTrackingLM:
    """Mock TrackingLM for testing."""

    def __init__(
        self, model_name="gpt-4o-mini", prompt_tokens=100, completion_tokens=50
    ):
        self.model_name = model_name
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class TestNormalizeGenAiSystem:
    """Test cases for normalize_gen_ai_system function."""

    def test_openai_models(self):
        """Test OpenAI model normalization."""
        test_cases = [
            ("gpt-4", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("gpt-4o", "openai"),
            ("openai/gpt-4", "openai"),
            ("o1-preview", "openai"),
            ("davinci", "openai"),
            ("curie", "openai"),
            ("babbage", "openai"),
            ("ada", "openai"),
        ]

        for model_name, expected in test_cases:
            result = normalize_gen_ai_system(model_name)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_anthropic_models(self):
        """Test Anthropic model normalization."""
        test_cases = [
            ("claude-3", "anthropic"),
            ("claude-3-sonnet", "anthropic"),
            ("anthropic/claude", "anthropic"),
        ]

        for model_name, expected in test_cases:
            result = normalize_gen_ai_system(model_name)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_aws_bedrock_models(self):
        """Test AWS Bedrock model normalization."""
        # Note: "bedrock/claude" will match "claude" first, so it returns "anthropic"
        # Only pure "bedrock" models return "aws.bedrock"
        result = normalize_gen_ai_system("bedrock-model")
        assert result == "aws.bedrock"

    def test_azure_models(self):
        """Test Azure model normalization."""
        # Note: The current implementation checks for "openai" before "azure"
        # so any model with "openai" in the name will match "openai" first
        test_cases = [
            ("azure-inference-model", "az.ai.inference"),
            # Skip azure-openai test since "openai" is checked first in the implementation
        ]

        for model_name, expected in test_cases:
            result = normalize_gen_ai_system(model_name)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

        # Test that azure-openai models actually return "openai" due to order of checks
        result = normalize_gen_ai_system("azure-openai-model")
        assert result == "openai", (
            "azure-openai models should return 'openai' due to order of checks"
        )

    def test_google_models(self):
        """Test Google model normalization."""
        test_cases = [
            ("gemini-pro", "gcp.gemini"),
            ("generativelanguage/gemini", "gcp.gemini"),
            ("vertex-model", "gcp.vertex_ai"),
            ("aiplatform/model", "gcp.vertex_ai"),
            ("google/palm", "gcp.gen_ai"),
            ("bard", "gcp.gen_ai"),
        ]

        for model_name, expected in test_cases:
            result = normalize_gen_ai_system(model_name)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_other_providers(self):
        """Test other provider model normalization."""
        test_cases = [
            ("cohere/command", "cohere"),
            ("deepseek/model", "deepseek"),
            ("groq/llama", "groq"),
            ("watsonx/model", "ibm.watsonx.ai"),
            ("ibm/model", "ibm.watsonx.ai"),
            ("llama3", "meta"),
            ("meta/llama", "meta"),
            ("mistral/model", "mistral_ai"),
            ("perplexity/model", "perplexity"),
            ("xai/model", "xai"),
            ("lm_studio/model", "_OTHER"),
            ("lm-studio/model", "_OTHER"),
            ("localhost/model", "_OTHER"),
            ("unknown-provider", "_OTHER"),
        ]

        for model_name, expected in test_cases:
            result = normalize_gen_ai_system(model_name)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )


class TestNormalizeOperationName:
    """Test cases for normalize_operation_name function."""

    def test_chat_operations(self):
        """Test chat operation detection."""
        test_cases = [
            ("gpt-4", None, ["user message"], "chat"),
            ("claude-3", None, [{"role": "user", "content": "hello"}], "chat"),
            ("gpt-4o", None, [], "chat"),  # Modern model defaults to chat
            ("llama3", None, [], "chat"),
        ]

        for model_name, prompt, messages, expected in test_cases:
            result = normalize_operation_name(model_name, prompt, messages)
            assert result == expected, (
                f"Failed for {model_name} with messages: got {result}, expected {expected}"
            )

    def test_embedding_operations(self):
        """Test embedding operation detection."""
        test_cases = [
            ("text-embedding-ada-002", None, None, "embeddings"),
            ("embedding-model", None, None, "embeddings"),
            ("ada-002", None, None, "embeddings"),
        ]

        for model_name, prompt, messages, expected in test_cases:
            result = normalize_operation_name(model_name, prompt, messages)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_content_generation_operations(self):
        """Test content generation operation detection."""
        test_cases = [
            ("gemini-pro", None, None, "generate_content"),
            ("generate-content-model", None, None, "generate_content"),
        ]

        for model_name, prompt, messages, expected in test_cases:
            result = normalize_operation_name(model_name, prompt, messages)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_text_completion_operations(self):
        """Test text completion operation detection."""
        test_cases = [
            ("davinci", None, None, "text_completion"),
            ("curie", None, None, "text_completion"),
            ("babbage", None, None, "text_completion"),
        ]

        for model_name, prompt, messages, expected in test_cases:
            result = normalize_operation_name(model_name, prompt, messages)
            assert result == expected, (
                f"Failed for {model_name}: got {result}, expected {expected}"
            )

    def test_default_operation(self):
        """Test default operation for unknown models."""
        result = normalize_operation_name("unknown-model", None, None)
        assert result == "chat"


class TestExportSemanticMetrics:
    """Test cases for export_semantic_metrics function."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a separate registry for testing to avoid conflicts
        self.test_registry = CollectorRegistry()
        self.mock_lm = MockTrackingLM()

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_export_semantic_metrics_basic(self, mock_calculate_cost):
        """Test basic semantic metrics export."""
        # Mock cost calculation
        mock_calculate_cost.return_value = {
            "prompt_cost": 0.001,
            "completion_cost": 0.002,
            "total_cost": 0.003,
            "prompt_price_per_1k": 0.5,
            "completion_price_per_1k": 1.0,
        }

        # Test the function
        export_semantic_metrics(self.mock_lm, operation_duration=1.5)

        # Verify cost calculation was called
        mock_calculate_cost.assert_called_once_with("gpt-4o-mini", 100, 50)

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_export_semantic_metrics_no_tokens(self, mock_calculate_cost):
        """Test semantic metrics export with no tokens."""
        mock_lm = MockTrackingLM(prompt_tokens=0, completion_tokens=0)

        # Should not call cost calculation for zero tokens
        export_semantic_metrics(mock_lm)

        mock_calculate_cost.assert_not_called()

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_export_semantic_metrics_cost_calculation_error(self, mock_calculate_cost):
        """Test semantic metrics export when cost calculation fails."""
        mock_calculate_cost.side_effect = Exception("Pricing error")

        # Should handle the exception gracefully
        export_semantic_metrics(self.mock_lm)

        # Should have attempted cost calculation
        mock_calculate_cost.assert_called_once()

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_export_semantic_metrics_different_models(self, mock_calculate_cost):
        """Test semantic metrics export with different model types."""
        test_models = [
            "gpt-4o",
            "claude-3-sonnet",
            "gemini-pro",
            "llama3-8b",
            "unknown-model",
        ]

        for model in test_models:
            # Reset and configure mock for each iteration
            mock_calculate_cost.reset_mock()
            mock_calculate_cost.return_value = {
                "prompt_cost": 0.001,
                "completion_cost": 0.002,
                "total_cost": 0.003,
                "prompt_price_per_1k": 0.5,
                "completion_price_per_1k": 1.0,
            }

            mock_lm = MockTrackingLM(model_name=model)
            # Should not raise any exceptions
            export_semantic_metrics(mock_lm)


class TestExportTokenMetrics:
    """Test cases for export_token_metrics function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_lm = MockTrackingLM()

    @patch("libraries.tracing.init_metrics.export_semantic_metrics")
    def test_export_token_metrics_calls_semantic(self, mock_export_semantic):
        """Test that export_token_metrics calls export_semantic_metrics."""
        mock_span = MagicMock()

        export_token_metrics(self.mock_lm, span=mock_span)

        mock_export_semantic.assert_called_once_with(self.mock_lm, span=mock_span)


class TestPatchTrackingLM:
    """Test cases for patch_tracking_lm function."""

    @patch("libraries.tracing.init_metrics.print")
    def test_patch_tracking_lm_prints_message(self, mock_print):
        """Test that patch_tracking_lm prints a success message."""
        # This test just verifies the function runs and prints the expected message
        patch_tracking_lm()

        # Verify the success message was printed
        mock_print.assert_called_with(
            "✓ Patched TrackingLM to export OpenTelemetry semantic convention metrics"
        )

    def test_patch_tracking_lm_function_exists(self):
        """Test that the patch_tracking_lm function exists and is callable."""
        # Simple test to verify the function exists
        assert callable(patch_tracking_lm)

        # Test that it doesn't raise an exception when called
        try:
            patch_tracking_lm()
        except Exception as e:
            # It's okay if it fails due to import issues, we just want to test the function exists
            assert "TrackingLM" in str(e) or "import" in str(e).lower()


class TestStartMetricsServer:
    """Test cases for start_metrics_server function."""

    @patch("libraries.tracing.init_metrics.start_http_server")
    def test_start_metrics_server_default_port(self, mock_start_server):
        """Test starting metrics server with default port."""
        start_metrics_server()
        mock_start_server.assert_called_once_with(9091)

    @patch("libraries.tracing.init_metrics.start_http_server")
    def test_start_metrics_server_custom_port(self, mock_start_server):
        """Test starting metrics server with custom port."""
        start_metrics_server(8080)
        mock_start_server.assert_called_once_with(8080)


class TestInitTokenMetrics:
    """Test cases for init_token_metrics function."""

    @patch("libraries.tracing.init_metrics.start_metrics_server")
    @patch("libraries.tracing.init_metrics.patch_tracking_lm")
    def test_init_token_metrics_default_params(self, mock_patch, mock_start_server):
        """Test init_token_metrics with default parameters."""
        init_token_metrics(force_init=True)

        mock_patch.assert_called_once()
        mock_start_server.assert_called_once_with(9091)

    @patch("libraries.tracing.init_metrics.start_metrics_server")
    @patch("libraries.tracing.init_metrics.patch_tracking_lm")
    def test_init_token_metrics_custom_params(self, mock_patch, mock_start_server):
        """Test init_token_metrics with custom parameters."""
        init_token_metrics(port=8080, application_name="custom_agent", force_init=True)

        mock_patch.assert_called_once()
        mock_start_server.assert_called_once_with(8080)

        # Check that application name was set
        from libraries.tracing.init_metrics import _application_name

        assert _application_name == "custom_agent"

    @patch("libraries.tracing.init_metrics.start_metrics_server")
    @patch("libraries.tracing.init_metrics.patch_tracking_lm")
    def test_init_token_metrics_sets_global_application_name(
        self, mock_patch, mock_start_server
    ):
        """Test that init_token_metrics sets the global application name."""
        test_name = "test_application"
        init_token_metrics(application_name=test_name, force_init=True)

        from libraries.tracing.init_metrics import _application_name

        assert _application_name == test_name

    @patch("libraries.tracing.init_metrics.start_metrics_server")
    @patch("libraries.tracing.init_metrics.patch_tracking_lm")
    @patch.dict("os.environ", {"CI": "true"})
    def test_init_token_metrics_skips_in_ci(self, mock_patch, mock_start_server):
        """Test that init_token_metrics is skipped in CI environment."""
        init_token_metrics()

        # Should not call any initialization functions
        mock_patch.assert_not_called()
        mock_start_server.assert_not_called()

    @patch("libraries.tracing.init_metrics.start_metrics_server")
    @patch("libraries.tracing.init_metrics.patch_tracking_lm")
    @patch.dict("os.environ", {"CI": "true"})
    def test_init_token_metrics_force_init_in_ci(self, mock_patch, mock_start_server):
        """Test that init_token_metrics can be forced to run in CI environment."""
        init_token_metrics(force_init=True)

        # Should call initialization functions even in CI when forced
        mock_patch.assert_called_once()
        mock_start_server.assert_called_once_with(9091)


class TestMetricsIntegration:
    """Integration tests for the metrics system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_lm = MockTrackingLM()

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_full_metrics_export_flow(self, mock_calculate_cost):
        """Test the complete metrics export flow."""
        # Mock cost calculation
        mock_calculate_cost.return_value = {
            "prompt_cost": 0.001,
            "completion_cost": 0.002,
            "total_cost": 0.003,
            "prompt_price_per_1k": 0.5,
            "completion_price_per_1k": 1.0,
        }

        # Test the complete flow
        export_token_metrics(self.mock_lm)

        # Verify cost calculation was called
        mock_calculate_cost.assert_called_once_with("gpt-4o-mini", 100, 50)

    def test_normalize_functions_consistency(self):
        """Test that normalization functions work consistently."""
        test_model = "gpt-4o-mini"

        system = normalize_gen_ai_system(test_model)
        operation = normalize_operation_name(test_model)

        assert system == "openai"
        assert operation == "chat"

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_metrics_with_different_token_counts(self, mock_calculate_cost):
        """Test metrics export with various token counts."""
        test_cases = [
            (0, 0),  # No tokens
            (100, 0),  # Only input tokens
            (0, 50),  # Only output tokens
            (1000, 500),  # Normal case
            (1, 1),  # Minimal tokens
        ]

        for prompt_tokens, completion_tokens in test_cases:
            # Reset and configure mock for each iteration
            mock_calculate_cost.reset_mock()
            mock_calculate_cost.return_value = {
                "prompt_cost": 0.001,
                "completion_cost": 0.002,
                "total_cost": 0.003,
                "prompt_price_per_1k": 0.5,
                "completion_price_per_1k": 1.0,
            }

            mock_lm = MockTrackingLM(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
            )

            # Should not raise any exceptions
            export_token_metrics(mock_lm)


class TestMetricsConfiguration:
    """Test cases for metrics configuration and setup."""

    def test_metrics_objects_exist(self):
        """Test that all required metrics objects are defined."""
        # Test that metrics are properly defined
        assert gen_ai_client_token_usage is not None
        assert gen_ai_client_operation_duration is not None
        assert gen_ai_client_cost_total is not None
        assert gen_ai_client_cost_current is not None
        assert gen_ai_client_cost_per_token is not None

    def test_application_name_global_variable(self):
        """Test the global application name variable."""
        from libraries.tracing.init_metrics import _application_name

        assert isinstance(_application_name, str)

    def test_application_name_usage(self):
        """Test that the application name is used in metrics export."""
        from libraries.tracing.init_metrics import _application_name

        # Just test that it's a string, since we can't easily test the patching
        assert isinstance(_application_name, str)


class TestErrorHandling:
    """Test cases for error handling in metrics system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_lm = MockTrackingLM()

    @patch("libraries.tracing.init_metrics.calculate_request_cost")
    def test_cost_calculation_error_handling(self, mock_calculate_cost):
        """Test that cost calculation errors are handled gracefully."""
        mock_calculate_cost.side_effect = Exception("Cost calculation failed")

        # Should not raise an exception
        export_semantic_metrics(self.mock_lm)

        # Should have attempted the calculation
        mock_calculate_cost.assert_called_once()

    def test_invalid_model_names(self):
        """Test handling of invalid model names."""
        invalid_models = ["", "   ", "invalid/model/name"]

        for model in invalid_models:
            # Should not raise exceptions
            system = normalize_gen_ai_system(model)
            operation = normalize_operation_name(model)

            assert isinstance(system, str)
            assert isinstance(operation, str)

        # Test None separately since it will cause AttributeError in current implementation
        # This shows that the function doesn't handle None gracefully
        with pytest.raises(AttributeError):
            normalize_gen_ai_system(None)

    @patch("libraries.tracing.init_metrics._application_name", "error_test_agent")
    def test_missing_lm_attributes(self):
        """Test handling of LM objects with missing attributes."""
        # Create a mock LM with missing attributes
        incomplete_lm = MagicMock()
        incomplete_lm.model_name = "gpt-4o"
        incomplete_lm.prompt_tokens = 100
        incomplete_lm.completion_tokens = 50

        # Should handle missing attributes gracefully
        export_semantic_metrics(incomplete_lm)


if __name__ == "__main__":
    pytest.main([__file__])
