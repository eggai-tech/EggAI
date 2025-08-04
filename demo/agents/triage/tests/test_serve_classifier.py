from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agents.triage.classifier_v7.classifier_v7 import ClassificationResult

# Import your FastAPI app and classifier from your app file
from agents.triage.classifier_v7.serve_classifier import app, init_classifier
from agents.triage.models import ClassifierMetrics, TargetAgent


@patch("agents.triage.classifier_v7.serve_classifier.mlflow.artifacts.download_artifacts", return_value="/fake/model/path")
@patch("agents.triage.classifier_v7.serve_classifier.Gemma3TextForSequenceClassification.from_pretrained")
@patch("agents.triage.classifier_v7.serve_classifier.AutoTokenizer.from_pretrained")
@patch("agents.triage.classifier_v7.serve_classifier.FinetunedClassifier")
def test_predict(mock_classifier_class, mock_tokenizer, mock_model, mock_download_artifacts):
    # Mock model and tokenizer
    mock_model.return_value = MagicMock()
    mock_tokenizer.return_value = MagicMock()
    mock_classifier_instance = MagicMock()

    # Mock return value
    mock_classifier_instance.classify.return_value = ClassificationResult(
        target_agent=TargetAgent.PolicyAgent,
        metrics=ClassifierMetrics(
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0.0
        )
    )
    mock_classifier_class.return_value = mock_classifier_instance

    # Initialize model using mocked components
    init_classifier()

    client = TestClient(app)

    # Prepare request payload
    payload = {
        "inputs": ["User: What is my policy coverage?"]
    }

    # Make POST request
    response = client.post("/invocations", json=payload)

    # Validate response
    assert response.status_code == 200
    assert response.json() == {
        "target_agent": "PolicyAgent",
        "metrics": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 0.0,
            'confidence': None
        }
    }

    # Validate that classify was called with correct input
    mock_classifier_instance.classify.assert_called_once_with("User: What is my policy coverage?")
