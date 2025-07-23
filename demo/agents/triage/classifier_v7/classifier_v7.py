import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import torch
from dotenv import load_dotenv
from peft import PeftModel
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
from triage.baseline_model.utils import setup_logging
from triage.classifier_v7.config import ClassifierV7Settings
from triage.classifier_v7.device_utils import (
    get_device_config,
    is_cuda_available,
    move_to_mps,
)

# import gemma3_wrapper so for so that Gemma3TextForSequenceClassification is registered
from agents.triage.classifier_v7.gemma3_wrapper import (
    Gemma3TextForSequenceClassification,
)
from agents.triage.models import ClassifierMetrics, TargetAgent

LABEL_TO_AGENT = {
    0: TargetAgent.BillingAgent,
    1: TargetAgent.ClaimsAgent,
    2: TargetAgent.PolicyAgent,
    3: TargetAgent.EscalationAgent,
    4: TargetAgent.ChattyAgent
}

logger = logging.getLogger(__name__)

load_dotenv()
v7_settings = ClassifierV7Settings()


@dataclass 
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class FinetunedClassifier:
    def __init__(self, model: Gemma3TextForSequenceClassification = None, tokenizer: AutoTokenizer = None):
        self.model = model
        self.tokenizer = tokenizer
    
    def _ensure_loaded(self):
        if self.model is not None:
            return
            
        # Check if fine-tuned model exists
        model_path = Path(v7_settings.output_dir)

        if model_path.exists() and (model_path / "config.json").exists():
            logger.info(f"Loading fine-tuned Gemma3 model from: {model_path}")
            base_model_name = v7_settings.get_model_name()
            self._load_finetuned_model(model_path, base_model_name)
        else:
            logger.info(f"Fine-tuned model not found at {model_path}")
            logger.info(f"Loading base model: {v7_settings.get_model_name()}")
            if v7_settings.use_qat_model:
                logger.info("Using QAT (Quantized Aware Training) model variant")
            self._load_base_model()

    def _load_finetuned_model(self, model_path, base_model_name):
        """Load fine-tuned sequence classification model"""
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        # Use shared device configuration
        device_map, dtype = get_device_config()
        
        # Load the fine-tuned sequence classification model directly
        base_model = AutoModelForSequenceClassification.from_pretrained(
            base_model_name,
            torch_dtype=dtype,
            device_map=device_map,
            attn_implementation="eager"
        )
        model = PeftModel.from_pretrained(base_model, model_path)
        
        # Move to mps if necessary
        self.model = move_to_mps(model, device_map)
        logger.info(f"Fine-tuned sequence classification model loaded from: {model_path}. Base model: {base_model_name}")
    

    def _load_base_model(self):
        """Load the base model via HuggingFace"""
        model_name = v7_settings.get_model_name()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        device_map, dtype = get_device_config()
        config = AutoConfig.from_pretrained(model_name)
        config.num_labels = v7_settings.n_classes  # Set number of classes for classification

        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            config=config,
            torch_dtype=dtype,
            device_map=device_map,
            load_in_4bit=v7_settings.use_4bit and not v7_settings.use_qat_model and is_cuda_available()  # 4-bit only on CUDA
        )

        # Move to appropriate device
        self.model = move_to_mps(model, device_map)
        logger.info(f"HuggingFace model for classification loaded: {model_name}")

    def classify(self, chat_history: str) -> TargetAgent:
        self._ensure_loaded()
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model failed to load")
        
        return self._sequence_classify(chat_history)

    def _sequence_classify(self, chat_history: str) -> TargetAgent:
        """Classification using sequence classification head"""

        inputs = self.tokenizer(chat_history, return_tensors="pt")
        
        # Move inputs to same device as model
        if torch.backends.mps.is_available():
            inputs = {k: v.to("mps") for k, v in inputs.items()}
        elif torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            predicted_class_id = predictions.argmax().item()
        
        return LABEL_TO_AGENT[predicted_class_id]


    def get_metrics(self) -> ClassifierMetrics:
        """Return empty metrics for local model (no token usage)"""
        return ClassifierMetrics(
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0
        )


# Global instance
_classifier = FinetunedClassifier()


def classifier_v7(chat_history: str) -> ClassificationResult:
    start_time = perf_counter()
    
    target_agent = _classifier.classify(chat_history)
    latency_ms = (perf_counter() - start_time) * 1000

    metrics = _classifier.get_metrics()
    metrics.latency_ms = latency_ms

    return ClassificationResult(
        target_agent=target_agent,
        metrics=metrics
    )

if __name__ == "__main__":
    setup_logging()
    result = classifier_v7(chat_history="User: I want to know my policy due date.")
    logger.info(f"Target Agent: {result.target_agent}")
    logger.info(f"Metrics: {result.metrics}")