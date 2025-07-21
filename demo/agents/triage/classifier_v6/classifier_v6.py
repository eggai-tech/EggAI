import logging
from dataclasses import dataclass
from time import perf_counter

import dspy
from dotenv import load_dotenv

from agents.triage.config import Settings
from agents.triage.models import ClassifierMetrics, TargetAgent

logger = logging.getLogger(__name__)

load_dotenv()
settings = Settings()


class TriageSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Chat conversation to classify")
    target_agent: TargetAgent = dspy.OutputField(desc="Target agent for routing")


@dataclass 
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class FinetunedClassifier:
    def __init__(self, model_id: str = None):
        self._model = None
        self._lm = None
        self._model_id = model_id or settings.classifier_v6_model_id
    
    def _ensure_loaded(self):
        if self._model is not None:
            return
            
        if not self._model_id:
            raise ValueError(
                "Fine-tuned model not configured. Provide model_id or set TRIAGE_CLASSIFIER_V6_MODEL_ID."
            )
        
        # Create fine-tuned language model
        self._lm = dspy.LM(f'openai/{self._model_id}', max_tokens=150)
        
        # Create classifier (minimal prompt - knowledge is in weights)
        self._model = dspy.Predict(TriageSignature)
        self._model.lm = self._lm
        
        logger.info("Fine-tuned classifier loaded")
    
    def classify(self, chat_history: str) -> TargetAgent:
        self._ensure_loaded()
        result = self._model(chat_history=chat_history) 
        return result.target_agent
    
    def get_metrics(self) -> ClassifierMetrics:
        if not self._lm:
            return ClassifierMetrics(
                total_tokens=0,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0
            )
            
        return ClassifierMetrics(
            total_tokens=getattr(self._lm, 'total_tokens', 0),
            prompt_tokens=getattr(self._lm, 'prompt_tokens', 0), 
            completion_tokens=getattr(self._lm, 'completion_tokens', 0),
            latency_ms=0
        )


# Global instance
_classifier = FinetunedClassifier()


def classifier_v6(chat_history: str) -> ClassificationResult:
    start_time = perf_counter()
    
    try:
        target_agent = _classifier.classify(chat_history)
        latency_ms = (perf_counter() - start_time) * 1000
        
        metrics = _classifier.get_metrics()
        metrics.latency_ms = latency_ms
        
        return ClassificationResult(
            target_agent=target_agent,
            metrics=metrics
        )
        
    except Exception as e:
        latency_ms = (perf_counter() - start_time) * 1000
        logger.warning("Classification failed, using ChattyAgent fallback: %s", e)
        
        return ClassificationResult(
            target_agent=TargetAgent.ChattyAgent,
            metrics=ClassifierMetrics(
                total_tokens=0,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms
            )
        )


if __name__ == "__main__":
    # Test the classifier
    result = classifier_v6(chat_history="User: I want to know my policy due date.")
    print(f"Target Agent: {result.target_agent}")
    print(f"Metrics: {result.metrics}")