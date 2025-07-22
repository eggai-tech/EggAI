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
        try:
            import os
            
            # Check if this is a sequence classification model or causal LM
            config_path = os.path.join(model_path, "config.json")
            is_sequence_classification = False
            
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Check if it has num_labels (sequence classification) or was trained as such
                    is_sequence_classification = 'num_labels' in config and config.get('num_labels', 0) > 1
            
            if is_sequence_classification:
                self._load_finetuned_sequence_model(model_path, base_model_name)
            else:
                self._load_finetuned_causal_model(model_path, base_model_name)
                
        except ImportError:
            logger.warning("HuggingFace transformers not available, falling back to base model")
            self._load_base_model()
    
    def _load_finetuned_sequence_model(self, model_path, base_model_name):
        """Load fine-tuned sequence classification model"""
        from transformers import (
            AutoConfig,
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # Use shared device configuration
        from .device_utils import get_device_config, move_to_device
        device_map, dtype = get_device_config()
        
        # Load config to get the correct number of labels
        config = AutoConfig.from_pretrained(model_path)
        
        # Load the fine-tuned sequence classification model directly
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            config=config,
            torch_dtype=dtype,
            device_map=device_map
        )
        
        # Move to appropriate device
        self.model = move_to_device(self.model, device_map)
        logger.info(f"Fine-tuned sequence classification model loaded with {config.num_labels} labels")
    
    def _load_finetuned_causal_model(self, model_path, base_model_name):
        """Load fine-tuned causal LM with LoRA adapters"""
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # Use shared device configuration
        from .device_utils import get_device_config, move_to_device
        device_map, dtype = get_device_config()
            
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=dtype,
            device_map=device_map
        )
        
        # Load LoRA adapters
        from peft import PeftModel
        self.model = PeftModel.from_pretrained(base_model, model_path)
        
        # Move to appropriate device
        self.model = move_to_device(self.model, device_map)
        logger.info("Fine-tuned causal LM with LoRA adapters loaded")
    
    def _load_base_model(self):
        """Load the base model via HuggingFace"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            model_name = v7_settings.get_model_name()
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                
            # Use shared device configuration
            from .device_utils import (
                get_device_config,
                is_cuda_available,
                move_to_device,
            )
            device_map, dtype = get_device_config()
            
            # Load as causal LM for generation-based classification
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map=device_map,
                load_in_4bit=v7_settings.use_4bit and not v7_settings.use_qat_model and is_cuda_available()  # 4-bit only on CUDA
            )
            
            # Move to appropriate device
            self.model = move_to_device(self.model, device_map)
            logger.info(f"Base HuggingFace causal LM loaded: {model_name}")
            
        except ImportError:
            logger.error("HuggingFace transformers not available")
            raise ImportError("HuggingFace transformers required for v7 classifier")
    
    
    def classify(self, chat_history: str) -> TargetAgent:
        self._ensure_loaded()
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model failed to load")
        
        return self._direct_classify(chat_history)
    
    def _direct_classify(self, chat_history: str) -> TargetAgent:
        """Direct classification using the appropriate method based on model type"""
        
        # Check if we have a sequence classification model with trained head
        if hasattr(self.model, 'score') and self._is_classification_head_trained():
            return self._sequence_classify(chat_history)
        else:
            # Use generation for base/fine-tuned causal LM models
            return self._generate_classify(chat_history)
    
    def _is_classification_head_trained(self) -> bool:
        """Check if the classification head has been trained (not random initialized)"""
        if not hasattr(self.model, 'score'):
            return False
            
        # Check if weights look trained (not close to random initialization)
        import torch
        score_weights = self.model.score.weight
        
        # Check if we have the right number of classes (5) - strong indicator it was trained
        if score_weights.shape[0] == 5:
            return True
        
        # If weights are very close to zero (typical random init), likely untrained
        if torch.abs(score_weights).mean().item() < 0.005:
            return False
            
        # If weights have very low variance, likely untrained (but be more lenient)
        if score_weights.var().item() < 0.0001:
            return False
            
        return True
    
    def _sequence_classify(self, chat_history: str) -> TargetAgent:
        """Classification using sequence classification head"""
        import torch
        
        inputs = self.tokenizer(chat_history, return_tensors="pt", truncation=True, max_length=512)
        
        # Move inputs to same device as model
        if torch.backends.mps.is_available():
            inputs = {k: v.to("mps") for k, v in inputs.items()}
        elif torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            predicted_class_id = predictions.argmax().item()
        
        # Map class ID to TargetAgent (assuming 5 classes)
        agent_mapping = {
            0: TargetAgent.BillingAgent,
            1: TargetAgent.ClaimsAgent, 
            2: TargetAgent.PolicyAgent,
            3: TargetAgent.EscalationAgent,
            4: TargetAgent.ChattyAgent
        }
        
        return agent_mapping.get(predicted_class_id, TargetAgent.ChattyAgent)
    
    def _generate_classify(self, chat_history: str) -> TargetAgent:
        """Fallback classification using generation (original method)"""
        import torch
        
        # Format prompt for classification
        formatted_prompt = f"<start_of_turn>user\n{chat_history}<end_of_turn>\n<start_of_turn>model\n"
        
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        
        # Move inputs to same device as model
        if torch.backends.mps.is_available():
            inputs = {k: v.to("mps") for k, v in inputs.items()}
        elif torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=20,
                temperature=0.1,
                do_sample=False,  # Use greedy decoding for consistency
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:], 
            skip_special_tokens=True
        ).strip()
        
        # Parse the response to extract agent name
        if "BillingAgent" in response:
            return TargetAgent.BillingAgent
        elif "ClaimsAgent" in response:
            return TargetAgent.ClaimsAgent
        elif "PolicyAgent" in response:
            return TargetAgent.PolicyAgent
        elif "EscalationAgent" in response:
            return TargetAgent.EscalationAgent
        else:
            return TargetAgent.ChattyAgent
    
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