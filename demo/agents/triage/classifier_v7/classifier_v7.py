import logging
from dataclasses import dataclass
from time import perf_counter

import dspy
from dotenv import load_dotenv

from agents.triage.models import ClassifierMetrics, TargetAgent

from .config import ClassifierV7Settings

logger = logging.getLogger(__name__)

load_dotenv()
v7_settings = ClassifierV7Settings()


class TriageSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Chat conversation to classify")
    target_agent: TargetAgent = dspy.OutputField(desc="Target agent for routing")


@dataclass 
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


class FinetunedClassifier:
    def __init__(self):
        self._model = None
        self._lm = None
    
    def _ensure_loaded(self):
        if self._model is not None:
            return
            
        # Check if fine-tuned model exists
        import os
        model_path = v7_settings.output_dir
        
        if os.path.exists(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
            logger.info(f"Loading fine-tuned Gemma3 model from: {model_path}")
            self._load_finetuned_model(model_path)
        else:
            logger.info(f"Fine-tuned model not found at {model_path}")
            logger.info(f"Loading base model: {v7_settings.get_model_name()}")
            if v7_settings.use_qat_model:
                logger.info("Using QAT (Quantized Aware Training) model variant")
            self._load_base_model()
    
    def _load_finetuned_model(self, model_path):
        """Load the fine-tuned HuggingFace model"""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Load base model first
            base_model_name = v7_settings.get_model_name()
            
            # Use shared device configuration
            from .device_utils import get_device_config, move_to_device
            device_map, dtype = get_device_config()
                
            base_model = AutoModelForSequenceClassification.from_pretrained(
                base_model_name,
                torch_dtype=dtype,
                device_map=device_map
            )
            
            # Load LoRA adapters
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(base_model, model_path)
            
            # Move to appropriate device
            self.model = move_to_device(self.model, device_map)
            
            # Create DSPy wrapper 
            try:
                self._lm = self._create_hf_lm()
                dspy.configure(lm=self._lm)
                self._model = dspy.Predict(TriageSignature)
                logger.info("Fine-tuned HuggingFace Gemma3 classifier loaded")
            except Exception as e:
                logger.warning(f"Failed to create DSPy LM: {e}")
                self._model = None
                self._lm = None
            
        except ImportError:
            logger.warning("HuggingFace transformers not available, falling back to base model")
            self._load_base_model()
    
    def _load_base_model(self):
        """Load the base model via HuggingFace or fallback to DSPy"""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            
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
                
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                torch_dtype=dtype,
                device_map=device_map,
                load_in_4bit=v7_settings.use_4bit and not v7_settings.use_qat_model and is_cuda_available()  # 4-bit only on CUDA
            )
            
            # Move to appropriate device
            self.model = move_to_device(self.model, device_map)
            
            # Create DSPy wrapper 
            try:
                self._lm = self._create_hf_lm()
                dspy.configure(lm=self._lm)
                self._model = dspy.Predict(TriageSignature)
                logger.info(f"Base HuggingFace model loaded: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to create DSPy LM: {e}")
                self._model = None
                self._lm = None
            
        except ImportError:
            logger.warning("HuggingFace transformers not available, using DSPy fallback")
            # Fallback to DSPy with dummy LM
            self._lm = None
            self._model = None
    
    def _create_hf_lm(self):
        """Create HuggingFace LM wrapper for DSPy"""
        class HuggingFaceLM(dspy.LM):
            def __init__(self, model, tokenizer):
                super().__init__("local/gemma")
                self.model = model
                self.tokenizer = tokenizer
                
            def basic_request(self, prompt, **kwargs):
                from .device_utils import is_cuda_available, is_mps_available, no_grad
                
                # Format prompt for classification
                formatted_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
                
                inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
                
                # Move inputs to same device as model
                if is_mps_available():
                    inputs = {k: v.to("mps") for k, v in inputs.items()}
                elif is_cuda_available():
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                
                with no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    
                # Get predicted class (0-4 for 5 agents)
                predicted_class = logits.argmax(dim=-1).item()
                agent_names = ['BillingAgent', 'ClaimsAgent', 'PolicyAgent', 'EscalationAgent', 'ChattyAgent']
                
                if 0 <= predicted_class < len(agent_names):
                    return [agent_names[predicted_class]]
                
                # Default fallback
                return ["ChattyAgent"]
        
        return HuggingFaceLM(self.model, self.tokenizer)
    
    def classify(self, chat_history: str) -> TargetAgent:
        self._ensure_loaded()
        if self.model is None or self.tokenizer is None:
            raise Exception("No LM is loaded.")
        
        # Direct classification without DSPy
        return self._direct_classify(chat_history)
    
    def _direct_classify(self, chat_history: str) -> TargetAgent:
        """Direct classification using the fine-tuned model"""
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