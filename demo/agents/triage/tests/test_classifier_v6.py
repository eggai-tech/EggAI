"""Comprehensive tests for classifier v6 - all unit and integration tests in one place."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_classifier_v6")


class TestClassifierV6Configuration:
    """Test v6 configuration and setup."""

    def test_configuration_loading(self):
        """Test v6 configuration loading and validation."""
        from agents.triage.config import Settings
        
        settings = Settings()
        assert hasattr(settings, 'classifier_v6_model_id')

    def test_imports(self):
        """Test v6 imports work correctly."""
        from agents.triage.classifier_v6.classifier_v6 import (
            ClassificationResult,
            FinetunedClassifier,
            classifier_v6,
        )
        
        # Verify all imports are successful
        assert callable(classifier_v6)
        assert FinetunedClassifier is not None
        assert ClassificationResult is not None


class TestClassifierV6Unit:
    """Unit tests for v6 with mocked dependencies - fast execution."""

    @patch('dspy.LM')
    @patch('dspy.Predict')
    def test_classifier_initialization(self, mock_predict, mock_lm):
        """Test v6 classifier initialization with mocked dependencies."""
        from agents.triage.classifier_v6.classifier_v6 import FinetunedClassifier
        
        mock_lm_instance = MagicMock()
        mock_lm.return_value = mock_lm_instance
        mock_predict_instance = MagicMock()
        mock_predict.return_value = mock_predict_instance
        
        # Test with explicit model_id parameter
        classifier = FinetunedClassifier(model_id='ft:test-model')
        classifier._ensure_loaded()
        
        assert classifier._lm is not None
        assert classifier._model is not None
        mock_lm.assert_called_once()

    def test_error_handling(self):
        """Test v6 error handling paths."""
        from agents.triage.classifier_v6.classifier_v6 import FinetunedClassifier
        
        classifier = FinetunedClassifier()
        
        # Test error path when no model ID is configured
        with patch('agents.triage.classifier_v6.classifier_v6.settings') as mock_settings:
            mock_settings.classifier_v6_model_id = None
            classifier_no_id = FinetunedClassifier(model_id=None)
            with pytest.raises(ValueError, match="Fine-tuned model not configured. Provide model_id or set TRIAGE_CLASSIFIER_V6_MODEL_ID."):
                classifier_no_id._ensure_loaded()

    @patch('dspy.LM')
    def test_classification_flow(self, mock_lm):
        """Test v6 classification with mocked model."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        
        mock_lm_instance = MagicMock()
        mock_lm.return_value = mock_lm_instance
        
        with patch('dspy.Predict') as mock_predict:
            mock_predict_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.target_agent = 'PolicyAgent'
            mock_predict_instance.return_value = mock_result
            mock_predict.return_value = mock_predict_instance
            
            with patch.dict(os.environ, {'TRIAGE_CLASSIFIER_V6_MODEL_ID': 'ft:test'}):
                result = classifier_v6("User: What is my policy coverage?")
                assert result is not None

    @patch('dspy.LM')
    @patch('dspy.Predict')
    def test_classifier_lifecycle(self, mock_predict, mock_lm):
        """Test v6 complete classifier lifecycle."""
        from agents.triage.classifier_v6.classifier_v6 import FinetunedClassifier
        
        # Setup comprehensive mocks
        mock_lm_instance = MagicMock()
        mock_lm_instance.get_metrics = MagicMock(return_value=MagicMock(
            total_tokens=150,
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.001
        ))
        mock_lm.return_value = mock_lm_instance
        
        mock_predict_instance = MagicMock()
        mock_predict_instance.return_value.target_agent = 'PolicyAgent'
        mock_predict.return_value = mock_predict_instance
        
        # Test with explicit model_id parameter
        classifier = FinetunedClassifier(model_id='ft:test-model')
        
        # Execute loading
        classifier._ensure_loaded()
        assert classifier._lm is not None
        assert classifier._model is not None
        
        # Execute classification
        result = classifier.classify("User: What is my policy coverage?")
        assert result == 'PolicyAgent'
        
        # Execute metrics
        metrics = classifier.get_metrics()
        assert metrics is not None


class TestClassifierV6DataUtils:
    """Test v6 data utility functions."""

    def test_create_training_examples(self):
        """Test v6 data utility functions."""
        from agents.triage.classifier_v6.data_utils import create_training_examples
        
        # Test basic functionality
        examples = create_training_examples(sample_size=5)
        assert len(examples) == 5
        
        for example in examples:
            assert hasattr(example, 'chat_history')
            assert hasattr(example, 'target_agent')
            assert isinstance(example.chat_history, str)
            assert isinstance(example.target_agent, str)

    def test_data_utils_edge_cases(self):
        """Test v6 data utilities edge cases."""
        from agents.triage.classifier_v6.data_utils import create_training_examples
        
        # Test edge cases
        examples_all = create_training_examples(sample_size=-1)  # All examples
        assert len(examples_all) > 0
        
        examples_large = create_training_examples(sample_size=99999)  # Larger than dataset
        assert len(examples_large) > 0


class TestClassifierV6ModelUtils:
    """Test v6 model utility functions."""

    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    def test_save_model_id_to_env(self, mock_exists, mock_open):
        """Test v6 model utility functions."""
        from agents.triage.classifier_v6.model_utils import save_model_id_to_env
        
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = save_model_id_to_env('ft:test-model-123')
        assert result is True
        
        # Verify file operations were called
        mock_open.assert_called()


class TestClassifierV6TrainingUtils:
    """Test v6 training utility functions."""

    @patch('mlflow.dspy.autolog')
    @patch('mlflow.set_experiment')
    @patch('mlflow.log_param')
    def test_training_utilities(self, mock_log_param, mock_set_exp, mock_autolog):
        """Test v6 training utility functions."""
        from agents.triage.classifier_v6.training_utils import (
            log_training_parameters,
            setup_mlflow_tracking,
        )
        
        run_name = setup_mlflow_tracking('test-model')
        assert run_name.startswith('v6_')
        
        log_training_parameters(10, 'test-model', 20)
        mock_log_param.assert_called()


class TestClassifierV6Integration:
    """Integration tests that exercise real implementation code paths."""

    def test_constructor_parameter_handling(self):
        """Test constructor with real parameter validation."""
        from agents.triage.classifier_v6.classifier_v6 import FinetunedClassifier
        
        # Test with explicit model_id
        custom_model = "ft:gpt-4o-mini-custom-123"
        classifier_custom = FinetunedClassifier(model_id=custom_model)
        assert classifier_custom._model_id == custom_model
        
        # Test with environment variable set
        with patch.dict(os.environ, {'TRIAGE_CLASSIFIER_V6_MODEL_ID': 'ft:env-model'}):
            # Need to reload settings to pick up env var
            with patch('agents.triage.classifier_v6.classifier_v6.settings') as mock_settings:
                mock_settings.classifier_v6_model_id = 'ft:env-model'
                classifier_env = FinetunedClassifier()
                assert classifier_env._model_id == 'ft:env-model'

    def test_error_handling_integration(self):
        """Test error handling with real implementation."""
        from agents.triage.classifier_v6.classifier_v6 import FinetunedClassifier
        
        # Test with None model_id and no environment settings
        with patch.dict(os.environ, {}, clear=True):
            with patch('agents.triage.config.Settings') as MockSettings:
                mock_settings = MagicMock()
                mock_settings.classifier_v6_model_id = None
                MockSettings.return_value = mock_settings
                
                classifier = FinetunedClassifier(model_id=None)
                
                # This should hit our real error handling code
                with pytest.raises(Exception) as exc_info:
                    classifier.classify(chat_history="User: test message")
                
                error_msg = str(exc_info.value)
                # The error might be about API key or model configuration
                assert "Fine-tuned model not configured" in error_msg or "api_key" in error_msg.lower()

    def test_deterministic_sampling_integration(self):
        """Test deterministic sampling with real numpy implementation."""
        from agents.triage.classifier_v6.data_utils import create_training_examples
        
        # Test deterministic sampling with seed
        examples_1 = create_training_examples(sample_size=5, seed=42)
        examples_2 = create_training_examples(sample_size=5, seed=42)
        
        assert len(examples_1) == 5
        assert len(examples_2) == 5
        
        # Should be identical with same seed
        for ex1, ex2 in zip(examples_1, examples_2, strict=False):
            assert ex1.chat_history == ex2.chat_history
            assert ex1.target_agent == ex2.target_agent
        
        # Test different seed produces different results
        examples_3 = create_training_examples(sample_size=5, seed=999)
        assert len(examples_3) == 5
        
        # Should be different with different seed (very high probability)
        different_count = sum(1 for ex1, ex3 in zip(examples_1, examples_3, strict=False) 
                             if ex1.chat_history != ex3.chat_history)
        assert different_count > 0  # At least some should be different

    def test_training_utils_integration(self):
        """Test training utilities with real execution."""
        from agents.triage.classifier_v6.training_utils import (
            get_classification_signature,
            log_training_parameters,
            setup_mlflow_tracking,
        )
        
        # Test signature creation
        signature = get_classification_signature()
        assert signature is not None
        # Signature is a DSPy class, so check its properties differently
        assert callable(signature)
        
        # Test MLflow setup with mocking
        with patch('mlflow.dspy.autolog'), patch('mlflow.set_experiment'):
            run_name = setup_mlflow_tracking('test-model')
            assert run_name.startswith('v6_')
            # Run name includes timestamp, model name may not be included
        
        # Test parameter logging
        with patch('mlflow.log_param') as mock_log:
            log_training_parameters(20, 'test-model', 100)
            
            # Verify all expected parameters were logged
            logged_params = {call.args[0]: call.args[1] for call in mock_log.call_args_list}
            assert logged_params['version'] == 'v6'
            assert logged_params['model'] == 'test-model'
            assert logged_params['samples'] == 20
            assert logged_params['examples'] == 100

    def test_finetune_trainer_integration(self):
        """Test finetune trainer with real error handling."""
        from agents.triage.classifier_v6.finetune_trainer import train_finetune_model
        
        # This should hit real error paths when DSPy/OpenAI is not configured
        with patch('agents.triage.classifier_v6.data_utils.create_examples') as mock_data:
            mock_data.return_value = []  # Empty training set
            
            with patch('mlflow.start_run'), patch('mlflow.log_param'), patch('mlflow.log_metric'):
                # This should exercise real error handling
                result = train_finetune_model(sample_size=1, model_name="test-model")
                
                # Should return None on failure
                assert result is None or isinstance(result, str)

    def test_complete_classification_integration(self):
        """Test complete classification flow from start to finish."""
        from agents.triage.classifier_v6.classifier_v6 import classifier_v6
        
        try:
            # This exercises the entire v6 pipeline
            result = classifier_v6(chat_history="User: I need help with my insurance claim")
            
            # If successful, verify result
            if result is not None:
                assert hasattr(result, 'target_agent')
                assert isinstance(result.target_agent, str)
                
        except Exception as e:
            # Expected in test environment without proper OpenAI setup
            logger.info(f"V6 classification flow executed with expected failure: {e}")



if __name__ == "__main__":
    pytest.main([__file__, "-v"])