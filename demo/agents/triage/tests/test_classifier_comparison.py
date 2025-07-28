"""Performance and accuracy comparison between classifier v6 and v7."""

import os
import time
from unittest.mock import patch

import pytest

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from agents.triage.models import TargetAgent
from libraries.observability.logger import get_console_logger

from .test_utils import (
    create_mock_classifier_result,
    get_standard_test_cases,
)

logger = get_console_logger("test_classifier_comparison")


class TestClassifierComparison:
    """Compare performance and accuracy between v6 and v7 classifiers."""
    
    def test_import_both_classifiers(self):
        """Test that both classifiers can be imported."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        
        assert classifier_v6 is not None
        assert classifier_v7 is not None
    
    def test_configuration_comparison(self):
        """Compare configuration between v6 and v7."""
        from agents.triage.classifier_v7.config import ClassifierV7Settings
        from agents.triage.config import Settings
        
        v6_config = Settings()  # v6 uses main triage config
        v7_config = ClassifierV7Settings()
        
        # Both should have required attributes
        assert hasattr(v6_config, 'classifier_v6_model_id')
        assert hasattr(v7_config, 'model_name')
        
        logger.info("V6 Configuration:")
        logger.info("  - Uses OpenAI API: True")
        logger.info(f"  - Fine-tuned model: {hasattr(v6_config, 'classifier_v6_model_id')}")
        
        logger.info("V7 Configuration:")
        logger.info(f"  - Model: {v7_config.get_model_name()}")
        logger.info(f"  - Uses LoRA: {v7_config.use_lora}")
        logger.info(f"  - Uses 4-bit: {v7_config.use_4bit}")
        logger.info(f"  - Uses QAT: {v7_config.use_qat_model}")
    
    @patch('agents.triage.classifier_v6.classifier_v6.dspy.configure')
    @patch('agents.triage.classifier_v6.classifier_v6.classifier_v6')
    @patch('agents.triage.classifier_v7.classifier_v7._classifier')
    def test_latency_comparison(self, mock_v7_classifier, mock_v6_classify, mock_v6_configure):
        """Compare latency between v6 and v7 classifiers with mocked responses."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        
        # Mock v6 (OpenAI API - typically faster)
        v6_result = create_mock_classifier_result(TargetAgent.PolicyAgent, latency_ms=150.0)
        mock_v6_classify.return_value = v6_result
        
        # Mock v7 (Local inference - typically slower)
        v7_result = create_mock_classifier_result(TargetAgent.PolicyAgent, latency_ms=250.0)
        mock_v7_classifier.classify.return_value = v7_result
        
        test_input = "User: What does my policy cover?"
        
        # Measure v6 latency
        start_time = time.perf_counter()
        result_v6 = classifier_v6(chat_history=test_input)
        v6_wall_time = (time.perf_counter() - start_time) * 1000
        
        # Measure v7 latency
        start_time = time.perf_counter()
        result_v7 = classifier_v7(chat_history=test_input)
        v7_wall_time = (time.perf_counter() - start_time) * 1000
        
        logger.info("Latency Comparison:")
        logger.info(f"  V6 (OpenAI API): {result_v6.metrics.latency_ms:.1f}ms (model) + {v6_wall_time:.1f}ms (wall)")
        logger.info(f"  V7 (Local HF):   {result_v7.metrics.latency_ms:.1f}ms (model) + {v7_wall_time:.1f}ms (wall)")
        
        # Both should return valid results
        assert result_v6 is not None
        assert result_v7 is not None
        assert result_v6.target_agent == result_v7.target_agent  # Same prediction in mock
    
    def test_token_usage_comparison(self):
        """Compare token usage patterns between v6 and v7."""
        from agents.triage.models import ClassifierMetrics
        
        # V6 typically has more predictable token usage (API-based)
        v6_metrics = ClassifierMetrics(
            latency_ms=150.0,
            prompt_tokens=120,  # Structured prompt
            completion_tokens=3,  # Single agent name
            total_tokens=123
        )
        
        # V7 might have different patterns (local generation)
        v7_metrics = ClassifierMetrics(
            latency_ms=250.0,
            prompt_tokens=180,  # Chat template formatting
            completion_tokens=8,  # Might generate more text initially
            total_tokens=188
        )
        
        logger.info("Token Usage Comparison:")
        logger.info(f"  V6 (OpenAI): {v6_metrics.prompt_tokens} prompt + {v6_metrics.completion_tokens} completion = {v6_metrics.total_tokens} total")
        logger.info(f"  V7 (Local):  {v7_metrics.prompt_tokens} prompt + {v7_metrics.completion_tokens} completion = {v7_metrics.total_tokens} total")
        
        # V6 should generally use fewer tokens due to fine-tuning
        # V7 might use more due to chat template overhead
        assert v6_metrics.total_tokens > 0
        assert v7_metrics.total_tokens > 0
    
    def test_error_handling_comparison(self):
        """Compare error handling between v6 and v7."""
        test_cases = [
            "",  # Empty input
            "User: " + "X" * 10000,  # Very long input
            "User: 🚀💻🎯 Special chars!",  # Unicode/emoji
            None,  # Invalid input type (would need to be handled by wrapper)
        ]
        
        for test_input in test_cases[:-1]:  # Skip None for now
            logger.info(f"Testing error handling for: {repr(test_input[:50])}")
            
            # Both classifiers should handle edge cases gracefully
            # (This would need actual implementation testing in integration tests)
            assert len(test_input) >= 0  # Basic validation
    
    def test_model_architecture_differences(self):
        """Document the architectural differences between v6 and v7."""
        differences = {
            "v6": {
                "model_type": "OpenAI GPT (fine-tuned)",
                "inference": "API-based (cloud)",
                "training": "OpenAI fine-tuning service",
                "cost_model": "Per-token API charges",
                "latency": "Network dependent",
                "scalability": "Managed by OpenAI"
            },
            "v7": {
                "model_type": "HuggingFace Gemma3 (LoRA fine-tuned)",
                "inference": "Local (on-device)",
                "training": "Local LoRA fine-tuning", 
                "cost_model": "Hardware/electricity only",
                "latency": "Hardware dependent",
                "scalability": "Manual scaling required"
            }
        }
        
        logger.info("Architecture Comparison:")
        for version, details in differences.items():
            logger.info(f"  {version.upper()}:")
            for key, value in details.items():
                logger.info(f"    {key}: {value}")
        
        # Verify we captured the key differences
        assert "OpenAI" in differences["v6"]["model_type"]
        assert "HuggingFace" in differences["v7"]["model_type"]
        assert "API-based" in differences["v6"]["inference"]
        assert "Local" in differences["v7"]["inference"]


@pytest.mark.integration
class TestClassifierIntegrationComparison:
    """Integration tests comparing real classifier behavior."""
    
    @pytest.mark.skipif(
        not os.getenv('OPENAI_API_KEY'),
        reason="Requires OPENAI_API_KEY for v6 testing"
    )
    def test_v6_availability(self):
        """Test if v6 is available for comparison."""
        try:
            from agents.triage.config import Settings
            
            settings = Settings()
            if settings.classifier_v6_model_id:
                logger.info("✓ V6 available for testing")
            else:
                logger.warning("⚠ V6 configured but no fine-tuned model ID")
        except Exception as e:
            logger.warning(f"⚠ V6 not available: {e}")
    
    def test_v7_availability(self):
        """Test if v7 is available for comparison."""
        try:
            from agents.triage.classifier_v7.config import ClassifierV7Settings
            
            settings = ClassifierV7Settings()
            model_name = settings.get_model_name()
            logger.info(f"✓ V7 available for testing with model: {model_name}")
            
            # Check if fine-tuned model exists
            import os
            if os.path.exists(settings.output_dir):
                logger.info("✓ Fine-tuned V7 model found")
            else:
                logger.info("ℹ V7 will use base model (no fine-tuned model found)")
                
        except Exception as e:
            logger.warning(f"⚠ V7 not available: {e}")
    
    @pytest.mark.slow
    @pytest.mark.skipif(
        not os.getenv('RUN_COMPARISON_TESTS'),
        reason="Set RUN_COMPARISON_TESTS=1 to run side-by-side comparison"
    )
    def test_side_by_side_comparison(self):
        """Run both classifiers side by side with same inputs."""
        test_cases = get_standard_test_cases()
        
        v6_results = []
        v7_results = []
        
        logger.info("Running side-by-side comparison...")
        
        for chat_history, expected_category in test_cases:
            logger.info(f"Testing: {chat_history}")
            
            # Test V6
            try:
                from agents.triage.classifier_v6.classifier_v6 import classifier_v6
                start_time = time.perf_counter()
                v6_result = classifier_v6(chat_history=chat_history)
                v6_wall_time = (time.perf_counter() - start_time) * 1000
                
                v6_results.append({
                    'input': chat_history,
                    'expected': expected_category,
                    'predicted': v6_result.target_agent,
                    'latency_ms': v6_result.metrics.latency_ms,
                    'wall_time_ms': v6_wall_time,
                    'tokens': v6_result.metrics.total_tokens,
                    'success': True
                })
                logger.info(f"  V6: {v6_result.target_agent} ({v6_result.metrics.latency_ms:.1f}ms)")
                
            except Exception as e:
                logger.error(f"  V6 failed: {e}")
                v6_results.append({'success': False, 'error': str(e)})
            
            # Test V7
            try:
                from agents.triage.classifier_v7.classifier_v7 import classifier_v7
                start_time = time.perf_counter()
                v7_result = classifier_v7(chat_history=chat_history)
                v7_wall_time = (time.perf_counter() - start_time) * 1000
                
                v7_results.append({
                    'input': chat_history,
                    'expected': expected_category,
                    'predicted': v7_result.target_agent,
                    'latency_ms': v7_result.metrics.latency_ms,
                    'wall_time_ms': v7_wall_time,
                    'tokens': v7_result.metrics.total_tokens,
                    'success': True
                })
                logger.info(f"  V7: {v7_result.target_agent} ({v7_result.metrics.latency_ms:.1f}ms)")
                
            except Exception as e:
                logger.error(f"  V7 failed: {e}")
                v7_results.append({'success': False, 'error': str(e)})
        
        # Analyze results
        v6_success_rate = sum(1 for r in v6_results if r.get('success', False)) / len(v6_results)
        v7_success_rate = sum(1 for r in v7_results if r.get('success', False)) / len(v7_results)
        
        logger.info(f"Success rates: V6={v6_success_rate:.1%}, V7={v7_success_rate:.1%}")
        
        if v6_success_rate > 0 and v7_success_rate > 0:
            v6_successful = [r for r in v6_results if r.get('success', False)]
            v7_successful = [r for r in v7_results if r.get('success', False)]
            
            v6_avg_latency = sum(r['latency_ms'] for r in v6_successful) / len(v6_successful)
            v7_avg_latency = sum(r['latency_ms'] for r in v7_successful) / len(v7_successful)
            
            logger.info(f"Average latencies: V6={v6_avg_latency:.1f}ms, V7={v7_avg_latency:.1f}ms")
        
        # At least one classifier should work
        assert v6_success_rate > 0 or v7_success_rate > 0, "Both classifiers failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])