import unittest
from unittest.mock import MagicMock, patch

import torch

from agents.triage.classifier_v8.classifier_v8 import (
    ClassificationResult,
    FinetunedRobertaClassifier,
    classifier_v8,
)
from agents.triage.models import TargetAgent


class TestClassifierV8(unittest.TestCase):

    def setUp(self):
        self.test_chat_history = "User: I want to know my policy due date."

    @patch('agents.triage.classifier_v8.classifier_v8.RobertaForSequenceClassification')
    @patch('agents.triage.classifier_v8.classifier_v8.AutoTokenizer')
    @patch('agents.triage.classifier_v8.classifier_v8.Path.exists')
    def test_load_base_model(self, mock_path_exists, mock_tokenizer, mock_model):
        mock_path_exists.return_value = False
        
        mock_tokenizer_instance = MagicMock()
        mock_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
        
        mock_model_instance = MagicMock()
        mock_model_instance.to.return_value = mock_model_instance
        mock_model.from_pretrained.return_value = mock_model_instance
        
        classifier = FinetunedRobertaClassifier()
        classifier._ensure_loaded()
        
        self.assertIsNotNone(classifier.model)
        self.assertIsNotNone(classifier.tokenizer)
        mock_tokenizer.from_pretrained.assert_called_once()
        mock_model.from_pretrained.assert_called_once()

    @patch('agents.triage.classifier_v8.classifier_v8.torch.cuda.is_available')
    @patch('agents.triage.classifier_v8.classifier_v8.RobertaForSequenceClassification')
    @patch('agents.triage.classifier_v8.classifier_v8.AutoTokenizer')
    @patch('agents.triage.classifier_v8.classifier_v8.Path.exists')
    def test_classify_base_model(self, mock_path_exists, mock_tokenizer, mock_model, mock_cuda):
        mock_path_exists.return_value = False
        mock_cuda.return_value = False
        
        mock_tokenizer_instance = MagicMock()
        mock_tokenizer_instance.return_value = {
            'input_ids': torch.tensor([[1, 2, 3]]),
            'attention_mask': torch.tensor([[1, 1, 1]])
        }
        mock_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
        
        mock_outputs = MagicMock()
        mock_outputs.logits = torch.tensor([[0.1, 0.9, 0.2, 0.1, 0.1]])
        
        mock_model_instance = MagicMock()
        mock_model_instance.to.return_value = mock_model_instance
        mock_model_instance.return_value = mock_outputs
        mock_model_instance.parameters.return_value = [torch.tensor([1.0])]
        mock_model.from_pretrained.return_value = mock_model_instance
        
        classifier = FinetunedRobertaClassifier()
        result = classifier.classify(self.test_chat_history)
        
        self.assertIsInstance(result, ClassificationResult)
        self.assertIsInstance(result.target_agent, TargetAgent)
        self.assertGreater(result.metrics.latency_ms, 0)

    def test_global_classifier_function(self):
        with patch('agents.triage.classifier_v8.classifier_v8._classifier.classify') as mock_classify:
            mock_result = ClassificationResult(
                target_agent=TargetAgent.CUSTOMER_SERVICE,
                metrics=MagicMock()
            )
            mock_classify.return_value = mock_result
            
            result = classifier_v8(self.test_chat_history)
            
            self.assertEqual(result, mock_result)
            mock_classify.assert_called_once_with(self.test_chat_history)

    @patch('agents.triage.classifier_v8.classifier_v8.PeftModel')
    @patch('agents.triage.classifier_v8.classifier_v8.RobertaForSequenceClassification')
    @patch('agents.triage.classifier_v8.classifier_v8.AutoTokenizer')
    @patch('agents.triage.classifier_v8.classifier_v8.Path.exists')
    def test_load_finetuned_model(self, mock_path_exists, mock_tokenizer, mock_base_model, mock_peft):
        mock_path_exists.return_value = True
        
        mock_tokenizer_instance = MagicMock()
        mock_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
        
        mock_base_model_instance = MagicMock()
        mock_base_model.from_pretrained.return_value = mock_base_model_instance
        
        mock_peft_model = MagicMock()
        mock_peft_model.to.return_value = mock_peft_model
        mock_peft.from_pretrained.return_value = mock_peft_model
        
        classifier = FinetunedRobertaClassifier()
        classifier._ensure_loaded()
        
        self.assertIsNotNone(classifier.model)
        self.assertIsNotNone(classifier.tokenizer)
        mock_peft.from_pretrained.assert_called_once()


if __name__ == '__main__':
    unittest.main()