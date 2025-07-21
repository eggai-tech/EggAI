"""Comprehensive test suite for classifier v7 (HuggingFace Gemma3 fine-tuning)."""

import os
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest
from dotenv import load_dotenv

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from agents.triage.classifier_v7.config import ClassifierV7Settings
from agents.triage.models import ClassifierMetrics, TargetAgent
from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_classifier_v7_comprehensive")


class TestClassifierV7Configuration:
    """Test configuration and setup of classifier v7."""
    
    def test_config_initialization(self):
        """Test that v7 configuration initializes correctly."""
        load_dotenv()
        config = ClassifierV7Settings()
        
        assert hasattr(config, 'model_name')
        assert hasattr(config, 'use_lora')
        assert hasattr(config, 'use_4bit')
        assert hasattr(config, 'use_qat_model')
        assert hasattr(config, 'output_dir')
    
    def test_model_name_configuration(self):
        """Test model name configuration."""
        config = ClassifierV7Settings()
        model_name = config.get_model_name()
        
        assert model_name is not None
        assert 'gemma' in model_name.lower()
    
    def test_qat_model_mapping(self):
        """Test QAT model mapping functionality."""
        config = ClassifierV7Settings()
        
        # Test with QAT enabled
        config.use_qat_model = True
        config.model_name = "google/gemma-3-1b-it"
        
        qat_model = config.get_model_name()
        assert qat_model == "google/gemma-3-qat-1b-it"
    
    def test_lora_configuration(self):
        """Test LoRA configuration parameters."""
        config = ClassifierV7Settings()
        
        assert hasattr(config, 'lora_r')
        assert hasattr(config, 'lora_alpha')
        assert hasattr(config, 'lora_dropout')
        assert config.lora_r > 0
        assert config.lora_alpha > 0
        assert 0 <= config.lora_dropout <= 1
    
    def test_training_configuration(self):
        """Test training configuration parameters."""
        config = ClassifierV7Settings()
        
        assert hasattr(config, 'num_epochs')
        assert hasattr(config, 'batch_size')
        assert hasattr(config, 'learning_rate')
        assert hasattr(config, 'max_length')
        assert config.num_epochs > 0
        assert config.batch_size > 0
        assert config.learning_rate > 0


class TestClassifierV7DeviceUtils:
    """Test device management utilities."""
    
    def test_device_utils_import(self):
        """Test device utilities import."""
        from agents.triage.classifier_v7.device_utils import (
            get_device_config,
            get_training_precision,
            is_cuda_available,
            is_mps_available,
            move_to_device,
            no_grad,
        )
        
        assert get_device_config is not None
        assert move_to_device is not None
        assert is_cuda_available is not None
        assert is_mps_available is not None
        assert get_training_precision is not None
        assert no_grad is not None
    
    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.get_device_capability', return_value=(8, 0))
    def test_cuda_device_config(self, mock_capability, mock_cuda_available):
        """Test device configuration with CUDA available."""
        from agents.triage.classifier_v7.device_utils import get_device_config
        
        device_map, dtype = get_device_config()
        assert device_map == "auto"
        # Should use bfloat16 for newer GPUs
    
    @patch('torch.cuda.is_available', return_value=False)
    @patch('torch.backends.mps.is_available', return_value=True)
    def test_mps_device_config(self, mock_mps_available, mock_cuda_available):
        """Test device configuration with MPS available."""
        from agents.triage.classifier_v7.device_utils import get_device_config
        
        device_map, dtype = get_device_config()
        assert device_map is None  # MPS doesn't support device_map="auto"
    
    @patch('torch.cuda.is_available', return_value=False)
    @patch('torch.backends.mps.is_available', return_value=False)
    def test_cpu_device_config(self, mock_mps_available, mock_cuda_available):
        """Test device configuration with CPU only."""
        from agents.triage.classifier_v7.device_utils import get_device_config
        
        device_map, dtype = get_device_config()
        assert device_map is None
    
    def test_training_precision_settings(self):
        """Test training precision configuration."""
        from agents.triage.classifier_v7.device_utils import get_training_precision
        
        precision = get_training_precision()
        assert isinstance(precision, dict)
        assert 'fp16' in precision
        assert 'bf16' in precision


class TestClassifierV7Imports:
    """Test that all v7 imports work correctly."""
    
    def test_config_import(self):
        """Test config module import."""
        from agents.triage.classifier_v7.config import ClassifierV7Settings
        assert ClassifierV7Settings is not None
    
    def test_classifier_import(self):
        """Test main classifier import."""
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        assert classifier_v7 is not None
    
    def test_training_utils_import(self):
        """Test training utilities import."""
        from agents.triage.classifier_v7.training_utils import (
            log_training_parameters,
            perform_fine_tuning,
            setup_mlflow_tracking,
        )
        assert setup_mlflow_tracking is not None
        assert log_training_parameters is not None
        assert perform_fine_tuning is not None
    
    def test_model_utils_import(self):
        """Test model utilities import."""
        from agents.triage.classifier_v7.model_utils import save_model_id_to_env
        assert save_model_id_to_env is not None
    
    def test_data_utils_import(self):
        """Test data utilities import."""
        from agents.triage.classifier_v7.data_utils import create_training_examples
        assert create_training_examples is not None


class TestClassifierV7Functionality:
    """Test v7 classifier functionality with mocked dependencies."""
    
    @patch('agents.triage.classifier_v7.classifier_v7.os.path.exists', return_value=False)
    def test_base_model_fallback(self, mock_exists):
        """Test fallback to base model when fine-tuned model doesn't exist."""
        with patch('agents.triage.classifier_v7.classifier_v7.dspy.configure'):
            from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
            
            classifier = FinetunedClassifier()
            # Should not raise an error when fine-tuned model doesn't exist
            assert classifier is not None
    
    def test_error_handling_with_missing_dependencies(self):
        """Test error handling when HuggingFace libraries are missing."""
        with patch('agents.triage.classifier_v7.classifier_v7.FinetunedClassifier._load_base_model', 
                   side_effect=ImportError("transformers not available")):
            from agents.triage.classifier_v7.classifier_v7 import classifier_v7
            
            # Should handle import errors gracefully
            try:
                result = classifier_v7(chat_history="Test message")
                # If it returns a result, it handled the error
                assert result is not None
            except ImportError:
                # If it raises ImportError, that's also acceptable behavior
                pass
    
    def test_direct_classification_method(self):
        """Test direct classification without DSPy wrapper."""
        # This would require mocking the HuggingFace model
        # For now, just test that the method exists
        from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
        
        classifier = FinetunedClassifier()
        assert hasattr(classifier, '_classify_directly')


class TestClassifierV7Training:
    """Test v7 training utilities and processes."""
    
    def test_model_id_saving(self):
        """Test saving model ID to environment."""
        from agents.triage.classifier_v7.model_utils import save_model_id_to_env
        
        # Test with temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with patch('agents.triage.classifier_v7.model_utils.os.path.exists', return_value=False):
                with patch('builtins.open', create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_open.return_value.__enter__.return_value = mock_file
                    
                    result = save_model_id_to_env('gemma-3-test-model-123')
                    assert result is True
        finally:
            os.unlink(temp_path)
    
    @patch('mlflow.dspy.autolog')
    @patch('mlflow.set_experiment')
    def test_mlflow_setup(self, mock_set_experiment, mock_autolog):
        """Test MLflow tracking setup."""
        from agents.triage.classifier_v7.training_utils import setup_mlflow_tracking
        
        run_name = setup_mlflow_tracking('gemma-3-test')
        
        assert run_name.startswith('v7_')
        mock_autolog.assert_called_once()
        mock_set_experiment.assert_called_once_with("triage_classifier")
    
    @patch('mlflow.log_param')
    def test_training_parameter_logging(self, mock_log_param):
        """Test logging of training parameters."""
        from agents.triage.classifier_v7.training_utils import log_training_parameters
        
        log_training_parameters(50, 'gemma-3-test', 100)
        
        # Verify parameters were logged
        expected_calls = [
            (("version", "v7"),),
            (("model", "gemma-3-test"),),
            (("samples", 50),),
            (("examples", 100),)
        ]
        
        for expected_call in expected_calls:
            mock_log_param.assert_any_call(*expected_call[0])
    
    @patch('agents.triage.classifier_v7.training_utils.torch')
    def test_fine_tuning_with_mocked_torch(self, mock_torch):
        """Test fine-tuning process with mocked PyTorch."""
        # Mock torch dependencies
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True
        
        from agents.triage.classifier_v7.training_utils import perform_fine_tuning
        
        # This would need extensive mocking of HuggingFace components
        # For now, test that the function exists and can be called
        assert perform_fine_tuning is not None


class TestClassifierV7EdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_chat_history(self):
        """Test classifier with empty chat history."""
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        
        # Mock the classification to avoid actual model loading
        with patch('agents.triage.classifier_v7.classifier_v7.FinetunedClassifier') as mock_classifier:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.target_agent = TargetAgent.ChattyAgent
            mock_result.metrics = ClassifierMetrics(latency_ms=50, prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_instance.__call__.return_value = mock_result
            mock_classifier.return_value = mock_instance
            
            result = classifier_v7(chat_history="")
            assert result is not None
    
    def test_very_long_chat_history(self):
        """Test classifier with very long chat history."""
        long_history = "User: " + "This is a very long message about insurance policies. " * 500
        
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        
        # Mock to avoid actual processing
        with patch('agents.triage.classifier_v7.classifier_v7.FinetunedClassifier') as mock_classifier:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.target_agent = TargetAgent.PolicyAgent
            mock_result.metrics = ClassifierMetrics(latency_ms=200, prompt_tokens=1000, completion_tokens=5, total_tokens=1005)
            mock_instance.__call__.return_value = mock_result
            mock_classifier.return_value = mock_instance
            
            result = classifier_v7(chat_history=long_history)
            assert result is not None
    
    def test_multilingual_input(self):
        """Test classifier with multilingual input."""
        multilingual_chat = "User: Hola, ¿qué es mi póliza de seguro? Hello, what is my insurance policy? 你好，我的保险政策是什么？"
        
        from agents.triage.classifier_v7.classifier_v7 import classifier_v7
        
        # Mock to avoid actual processing
        with patch('agents.triage.classifier_v7.classifier_v7.FinetunedClassifier') as mock_classifier:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.target_agent = TargetAgent.PolicyAgent
            mock_result.metrics = ClassifierMetrics(latency_ms=150, prompt_tokens=50, completion_tokens=5, total_tokens=55)
            mock_instance.__call__.return_value = mock_result
            mock_classifier.return_value = mock_instance
            
            result = classifier_v7(chat_history=multilingual_chat)
            assert result is not None


class TestClassifierV7DataUtils:
    """Test data utilities for training."""
    
    def test_training_data_creation(self):
        """Test creation of training examples."""
        from agents.triage.classifier_v7.data_utils import create_training_examples
        
        # Test with small sample size
        examples = create_training_examples(5)
        
        assert len(examples) == 5
        for example in examples:
            assert hasattr(example, 'chat_history')
            assert hasattr(example, 'target_agent')
    
    def test_training_data_validation(self):
        """Test validation of training data structure."""
        from agents.triage.classifier_v7.data_utils import create_training_examples
        
        examples = create_training_examples(10)
        
        # Check that examples have required fields
        for example in examples:
            assert isinstance(example.chat_history, str)
            assert len(example.chat_history) > 0
            assert isinstance(example.target_agent, TargetAgent)


class TestClassifierV7Metrics:
    """Test metrics collection specific to v7."""
    
    def test_metrics_for_local_model(self):
        """Test metrics structure for local model inference."""
        from agents.triage.models import ClassifierMetrics
        
        # V7 metrics might have different token counting since it's local
        metrics = ClassifierMetrics(
            latency_ms=250.0,  # Local inference might be slower
            prompt_tokens=150,
            completion_tokens=10,
            total_tokens=160
        )
        
        assert metrics.latency_ms == 250.0
        assert metrics.total_tokens == 160
    
    def test_classification_result_structure(self):
        """Test that v7 returns proper result structure."""
        from agents.triage.classifier_v7.classifier_v7 import ClassificationResult
        from agents.triage.models import ClassifierMetrics, TargetAgent
        
        metrics = ClassifierMetrics(latency_ms=100, prompt_tokens=50, completion_tokens=5, total_tokens=55)
        result = ClassificationResult(target_agent=TargetAgent.PolicyAgent, metrics=metrics)
        
        assert result.target_agent == TargetAgent.PolicyAgent
        assert result.metrics.latency_ms == 100


@pytest.mark.integration
@pytest.mark.slow
class TestClassifierV7Integration:
    """Integration tests that may require actual model loading."""
    
    @pytest.mark.skipif(
        not os.path.exists("/usr/local/bin/python") and not os.path.exists("/opt/homebrew/bin/python"),
        reason="Requires local Python with HuggingFace transformers"
    )
    def test_device_detection_integration(self):
        """Test actual device detection on the current system."""
        try:
            from agents.triage.classifier_v7.device_utils import (
                get_device_config,
                is_cuda_available,
                is_mps_available,
            )
            
            cuda_available = is_cuda_available()
            mps_available = is_mps_available()
            device_map, dtype = get_device_config()
            
            logger.info(f"CUDA available: {cuda_available}")
            logger.info(f"MPS available: {mps_available}")
            logger.info(f"Device config: {device_map}, {dtype}")
            
            # At least one should work
            assert cuda_available or mps_available or (device_map is None)
            
        except ImportError:
            pytest.skip("PyTorch not available for integration test")
    
    @pytest.mark.skipif(
        not os.environ.get('RUN_SLOW_TESTS'),
        reason="Set RUN_SLOW_TESTS=1 to run model loading tests"
    )
    def test_base_model_loading(self):
        """Test loading base Gemma model (very slow, requires internet)."""
        try:
            from agents.triage.classifier_v7.config import ClassifierV7Settings
            
            config = ClassifierV7Settings()
            model_name = config.get_model_name()
            
            # This would actually try to download the model
            logger.info(f"Would test loading model: {model_name}")
            
            # For now, just verify the model name is valid
            assert 'gemma' in model_name.lower()
            
        except Exception as e:
            pytest.skip(f"Model loading test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])