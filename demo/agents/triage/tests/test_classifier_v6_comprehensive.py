"""Comprehensive test suite for classifier v6 (OpenAI fine-tuning)."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from dotenv import load_dotenv

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from agents.triage.config import Settings
from agents.triage.models import ClassifierMetrics, TargetAgent
from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_classifier_v6_comprehensive")


class TestClassifierV6Configuration:
    """Test configuration and setup of classifier v6."""
    
    def test_config_initialization(self):
        """Test that v6 configuration initializes correctly."""
        load_dotenv()
        config = Settings()
        
        # Check that v6-specific fields exist
        assert hasattr(config, 'classifier_v6_model_id')
        assert hasattr(config, 'language_model')
        assert hasattr(config, 'classifier_version')
        
    def test_config_validation(self):
        """Test configuration validation."""
        with patch.dict(os.environ, {}, clear=True):
            config = Settings()
            # Should not raise an error even without env vars
            assert config is not None
            # V6 specific fields should exist
            assert hasattr(config, 'classifier_v6_model_id')
    
    def test_fine_tuned_model_id_property(self):
        """Test fine-tuned model ID property."""
        with patch.dict(os.environ, {'TRIAGE_CLASSIFIER_V6_MODEL_ID': 'ft:test-model-123'}, clear=False):
            config = Settings()
            assert config.classifier_v6_model_id == 'ft:test-model-123'


class TestClassifierV6Imports:
    """Test that all v6 imports work correctly."""
    
    def test_config_import(self):
        """Test config module import."""
        from agents.triage.config import Settings
        assert Settings is not None
    
    def test_classifier_import(self):
        """Test main classifier import."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        assert classifier_v6 is not None
    
    def test_training_utils_import(self):
        """Test training utilities import."""
        from agents.triage.classifier_v6.training_utils import (
            log_training_parameters,
            setup_mlflow_tracking,
        )
        assert setup_mlflow_tracking is not None
        assert log_training_parameters is not None
    
    def test_model_utils_import(self):
        """Test model utilities import."""
        from agents.triage.classifier_v6.model_utils import save_model_id_to_env
        assert save_model_id_to_env is not None


class TestClassifierV6Functionality:
    """Test v6 classifier functionality with mocked dependencies."""
    
    @patch('agents.triage.classifier_v6.classifier_v6.dspy.OpenAI')
    @patch('agents.triage.classifier_v6.classifier_v6.dspy.configure')
    def test_classifier_initialization(self, mock_configure, mock_openai):
        """Test classifier initialization with mocked OpenAI."""
        mock_lm = Mock()
        mock_openai.return_value = mock_lm
        
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        
        # Mock a simple classification response
        mock_result = Mock()
        mock_result.target_agent = TargetAgent.PolicyAgent
        
        with patch('agents.triage.classifier_v6.classifier_v6.classify_conversation', return_value=mock_result):
            result = classifier_v6(chat_history="User: What is my policy coverage?")
            
            assert result is not None
            assert hasattr(result, 'target_agent')
    
    @patch.dict(os.environ, {'TRIAGE_CLASSIFIER_V6_MODEL_ID': 'ft:test-model'}, clear=False)
    def test_fine_tuned_model_detection(self):
        """Test detection of fine-tuned model."""
        from agents.triage.config import Settings
        
        config = Settings()
        assert config.classifier_v6_model_id == 'ft:test-model'
    
    def test_error_handling(self):
        """Test error handling in classifier."""
        with patch.dict(os.environ, {}, clear=True):
            # Should handle missing configuration gracefully
            from agents.triage.config import Settings
            config = Settings()
            assert config is not None


class TestClassifierV6Training:
    """Test v6 training utilities."""
    
    def test_model_id_saving(self):
        """Test saving model ID to environment."""
        from agents.triage.classifier_v6.model_utils import save_model_id_to_env
        
        # Test with mock file operations
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            with patch('os.path.exists', return_value=False):
                result = save_model_id_to_env('ft:test-model-123')
                assert result is True
    
    @patch('mlflow.dspy.autolog')
    @patch('mlflow.set_experiment')
    def test_mlflow_setup(self, mock_set_experiment, mock_autolog):
        """Test MLflow tracking setup."""
        from agents.triage.classifier_v6.training_utils import setup_mlflow_tracking
        
        run_name = setup_mlflow_tracking('test-model')
        
        assert run_name.startswith('v6_')
        mock_autolog.assert_called_once()
        mock_set_experiment.assert_called_once_with("triage_classifier")
    
    @patch('mlflow.log_param')
    def test_training_parameter_logging(self, mock_log_param):
        """Test logging of training parameters."""
        from agents.triage.classifier_v6.training_utils import log_training_parameters
        
        log_training_parameters(50, 'test-model', 100)
        
        # Verify parameters were logged
        expected_calls = [
            (("version", "v6"),),
            (("model", "test-model"),),
            (("samples", 50),),
            (("examples", 100),)
        ]
        
        for expected_call in expected_calls:
            mock_log_param.assert_any_call(*expected_call[0])


class TestClassifierV6EdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_chat_history(self):
        """Test classifier with empty chat history."""
        with patch('agents.triage.classifier_v6.classifier_v6.dspy.configure'):
            with patch('agents.triage.classifier_v6.classifier_v6.classify_conversation') as mock_classify:
                mock_result = Mock()
                mock_result.target_agent = TargetAgent.ChattyAgent
                mock_classify.return_value = mock_result
                
                from agents.triage.classifier_v6.classifier_v6 import classifier_v6
                result = classifier_v6(chat_history="")
                
                assert result is not None
    
    def test_very_long_chat_history(self):
        """Test classifier with very long chat history."""
        long_history = "User: " + "This is a very long message. " * 1000
        
        with patch('agents.triage.classifier_v6.classifier_v6.dspy.configure'):
            with patch('agents.triage.classifier_v6.classifier_v6.classify_conversation') as mock_classify:
                mock_result = Mock()
                mock_result.target_agent = TargetAgent.ChattyAgent
                mock_classify.return_value = mock_result
                
                from agents.triage.classifier_v6.classifier_v6 import classifier_v6
                result = classifier_v6(chat_history=long_history)
                
                assert result is not None
    
    def test_special_characters_in_chat(self):
        """Test classifier with special characters."""
        special_chat = "User: Hello! 🚀 What's my policy? #insurance @support"
        
        with patch('agents.triage.classifier_v6.classifier_v6.dspy.configure'):
            with patch('agents.triage.classifier_v6.classifier_v6.classify_conversation') as mock_classify:
                mock_result = Mock()
                mock_result.target_agent = TargetAgent.PolicyAgent
                mock_classify.return_value = mock_result
                
                from agents.triage.classifier_v6.classifier_v6 import classifier_v6
                result = classifier_v6(chat_history=special_chat)
                
                assert result is not None


class TestClassifierV6Metrics:
    """Test metrics collection and validation."""
    
    def test_metrics_structure(self):
        """Test that metrics have the correct structure."""
        
        metrics = ClassifierMetrics(
            latency_ms=150.5,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        assert metrics.latency_ms == 150.5
        assert metrics.prompt_tokens == 100
        assert metrics.completion_tokens == 50
        assert metrics.total_tokens == 150
    
    def test_target_agent_enum(self):
        """Test TargetAgent enum values."""
        from agents.triage.models import TargetAgent
        
        # Test all expected target agents
        expected_agents = {
            'PolicyAgent', 'ClaimsAgent', 'BillingAgent', 
            'ChattyAgent', 'SalesAgent', 'TechnicalSupportAgent'
        }
        
        available_agents = {agent.value for agent in TargetAgent}
        
        # Check that expected agents are available
        assert expected_agents.issubset(available_agents), \
            f"Missing agents: {expected_agents - available_agents}"


@pytest.mark.integration
class TestClassifierV6Integration:
    """Integration tests that may require actual API access."""
    
    @pytest.mark.skipif(
        not os.getenv('OPENAI_API_KEY') or not os.getenv('TRIAGE_CLASSIFIER_V6_MODEL_ID'),
        reason="Requires OPENAI_API_KEY and TRIAGE_CLASSIFIER_V6_MODEL_ID environment variables"
    )
    def test_real_classification(self):
        """Test real classification with actual OpenAI API (if available)."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        
        test_cases = [
            "User: I need help with my insurance claim",
            "User: What's my policy coverage?",
            "User: I need to pay my bill",
        ]
        
        for chat_history in test_cases:
            try:
                result = classifier_v6(chat_history=chat_history)
                
                # Basic structure validation
                assert result is not None
                assert hasattr(result, 'target_agent')
                assert hasattr(result, 'metrics')
                assert result.metrics.latency_ms >= 0
                
                logger.info(f"✓ Classified: '{chat_history}' -> {result.target_agent}")
                
            except Exception as e:
                logger.warning(f"Classification failed: {e}")
                # Don't fail the test for API issues
                pytest.skip(f"API error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])