import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Optional

import torch
from dotenv import load_dotenv
from transformers import AutoTokenizer, RobertaForSequenceClassification

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v8.config import ClassifierV8Settings
from agents.triage.data_sets.loader import ID2LABEL
from agents.triage.models import ClassifierMetrics, TargetAgent

logger = logging.getLogger(__name__)

load_dotenv()
v8_settings = ClassifierV8Settings()


@dataclass
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class FinetunedRobertaClassifier:
    def __init__(self, model_path: Optional[str] = None):
        device = v8_settings.device
        if device not in ["mps", "cuda", "cpu"]:
            raise ValueError(f"Invalid device specified: {device}. Must be 'mps', 'cuda', or 'cpu'.")
        self.device = device

        if model_path is not None and Path(model_path).exists():
            logger.info(f"Loading fine-tuned RoBERTa model from: {model_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)

            self.model = RobertaForSequenceClassification.from_pretrained(
                model_path,
                num_labels=len(ID2LABEL)
            )

            self.model = self.model.to(device)
            self.model.eval()

            logger.info(f"Fine-tuned LoRA RoBERTa model loaded from: {model_path}")
        else:
            logger.warning(f"Fine-tuned model not found at {model_path}")
            logger.warning(f"Loading base model with random classification head: {v8_settings.model_name}")
            model_name = v8_settings.model_name
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)

            self.model = RobertaForSequenceClassification.from_pretrained(
                model_name,
                num_labels=v8_settings.n_classes
            )

            self.model = self.model.to(device)
            self.model.eval()

    def classify(self, chat_history: str) -> ClassificationResult:
        start_time = perf_counter()
        target_agent = self._sequence_classify(chat_history)
        latency_ms = (perf_counter() - start_time) * 1000

        metrics = ClassifierMetrics(
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency_ms
        )

        return ClassificationResult(target_agent=target_agent, metrics=metrics)

    def _sequence_classify(self, chat_history: str) -> TargetAgent:
        inputs = self.tokenizer(
            chat_history,
            return_tensors="pt",
            truncation=True,
            padding=True
        )

        # move inputs to the same device as the model
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            predicted_class_id = predictions.argmax().item()

        return ID2LABEL[predicted_class_id]

    def get_metrics(self) -> ClassifierMetrics:
        return ClassifierMetrics(
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0
        )


_classifier = None


def classifier_v8(chat_history: str) -> ClassificationResult:
    # Ensure the classifier is loaded
    global _classifier
    if _classifier is None:
        _classifier = FinetunedRobertaClassifier()
    return _classifier.classify(chat_history)


if __name__ == "__main__":
    setup_logging()
    result = classifier_v8(chat_history="User: I want to know my policy due date.")
    logger.info(f"Target Agent: {result.target_agent}")
    logger.info(f"Metrics: {result.metrics}")
