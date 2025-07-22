import logging
from dataclasses import dataclass
from time import perf_counter

from dotenv import load_dotenv

from agents.triage.models import ClassifierMetrics, TargetAgent

from .config import ClassifierV7Settings

logger = logging.getLogger(__name__)

load_dotenv()
v7_settings = ClassifierV7Settings()


@dataclass 
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class FinetunedClassifier:
    def __init__(self):
        self.model = None
        self.tokenizer = None
    
    def _ensure_loaded(self):
        if self.model is not None:
            return
            
        # Check if fine-tuned model exists
        import os
        model_path = v7_settings.output_dir
        
        try:
            if os.path.exists(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
                logger.info(f"Loading fine-tuned Gemma3 model from: {model_path}")
                base_model_name = v7_settings.get_model_name()
                self._load_finetuned_model(model_path, base_model_name)
            else:
                logger.info(f"Fine-tuned model not found at {model_path}")
                logger.info(f"Loading base model: {v7_settings.get_model_name()}")
                if v7_settings.use_qat_model:
                    logger.info("Using QAT (Quantized Aware Training) model variant")
                self._load_base_model()
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e
    
    def _load_finetuned_model(self, model_path, base_model_name):
        """Load the fine-tuned HuggingFace model"""
        from peft import PeftModel
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        from .device_utils import get_device_config, move_to_device
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # Use shared device configuration
        device_map, dtype = get_device_config()
            
        base_model = AutoModelForSequenceClassification.from_pretrained(
            base_model_name,
            torch_dtype=dtype,
            device_map=device_map,
            num_labels=5  # BillingAgent, ClaimsAgent, PolicyAgent, EscalationAgent, ChattyAgent
        )
        
        # Load LoRA adapters
        self.model = PeftModel.from_pretrained(base_model, model_path)
        
        # Move to appropriate device
        self.model = move_to_device(self.model, device_map)
        
        logger.info("Fine-tuned HuggingFace Gemma3 classifier loaded")
    
    def _load_base_model(self):
        """Load the base HuggingFace model"""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        from .device_utils import get_device_config, is_cuda_available, move_to_device
        
        model_name = v7_settings.get_model_name()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        # Use shared device configuration
        device_map, dtype = get_device_config()
            
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map=device_map,
            num_labels=5,  # BillingAgent, ClaimsAgent, PolicyAgent, EscalationAgent, ChattyAgent
            load_in_4bit=v7_settings.use_4bit and not v7_settings.use_qat_model and is_cuda_available()  # 4-bit only on CUDA
        )
        
        # Move to appropriate device
        self.model = move_to_device(self.model, device_map)
        logger.info(f"Base HuggingFace model loaded: {model_name}")
    
    
    def classify(self, chat_history: str) -> TargetAgent:
        self._ensure_loaded()
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model failed to load")
        
        return self._classify(chat_history)
    
    def _classify(self, chat_history: str) -> TargetAgent:
        """Classification using model logits"""
        import torch
        
        # Class mapping for classification model
        CLASS_TO_AGENT = {
            0: TargetAgent.BillingAgent,
            1: TargetAgent.ClaimsAgent, 
            2: TargetAgent.PolicyAgent,
            3: TargetAgent.EscalationAgent,
            4: TargetAgent.ChattyAgent
        }
        
        # Tokenize input text for classification
        inputs = self.tokenizer(chat_history, return_tensors="pt", truncation=True, max_length=512)
        
        # Move inputs to same device as model
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            predicted_class_id = torch.argmax(outputs.logits, dim=-1).item()
        
        return CLASS_TO_AGENT.get(predicted_class_id, TargetAgent.ChattyAgent)
    
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
    result = classifier_v7(chat_history="User: I want to know my policy due date.")
    print(f"Target Agent: {result.target_agent}")
    print(f"Metrics: {result.metrics}")