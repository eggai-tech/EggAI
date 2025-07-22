"""Custom Gemma3 sequence classification models for HuggingFace Transformers.

This module provides custom sequence classification implementations for Gemma3 models
since HuggingFace doesn't natively support Gemma3 for sequence classification tasks.
These implementations are automatically registered with AutoModelForSequenceClassification.
"""

import torch
import torch.nn as nn
from transformers import (
    AutoModelForSequenceClassification,
    Gemma3Config,
    Gemma3ForCausalLM,
)
from transformers.modeling_outputs import SequenceClassifierOutputWithPast


class Gemma3ForSequenceClassification(Gemma3ForCausalLM):
    """Gemma3 model with a sequence classification head on top (a linear layer on top of pooled last hidden states).
    
    This model inherits from Gemma3ForCausalLM and adds a classification head for
    sequence classification tasks like sentiment analysis, text classification, etc.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.score = nn.Linear(config.hidden_size, config.num_labels, bias=False)
        
        # Initialize weights and apply final processing
        self.post_init()
    
    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        inputs_embeds=None,
        labels=None,
        use_cache=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
        **kwargs,
    ):
        """Forward pass for sequence classification."""
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict
        
        # Get transformer outputs
        transformer_outputs = self.model(
            input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_values=past_key_values,
            inputs_embeds=inputs_embeds,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )
        
        hidden_states = transformer_outputs[0]
        
        # Simple pooling: just use the last token for each sequence
        if input_ids is not None:
            batch_size = input_ids.shape[0]
        else:
            batch_size = inputs_embeds.shape[0]
        
        # Use last token hidden state for classification
        pooled_hidden_states = hidden_states[:, -1, :]  # [batch_size, hidden_size]
        logits = self.score(pooled_hidden_states)  # [batch_size, num_labels]
        
        loss = None
        if labels is not None:
            if self.config.problem_type is None:
                if self.num_labels == 1:
                    self.config.problem_type = "regression"
                elif self.num_labels > 1 and (labels.dtype == torch.long or labels.dtype == torch.int):
                    self.config.problem_type = "single_label_classification"
                else:
                    self.config.problem_type = "multi_label_classification"
            
            if self.config.problem_type == "regression":
                loss_fct = nn.MSELoss()
                if self.num_labels == 1:
                    loss = loss_fct(logits.squeeze(), labels.squeeze())
                else:
                    loss = loss_fct(logits, labels)
            elif self.config.problem_type == "single_label_classification":
                loss_fct = nn.CrossEntropyLoss()
                loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))
            elif self.config.problem_type == "multi_label_classification":
                loss_fct = nn.BCEWithLogitsLoss()
                loss = loss_fct(logits, labels)
        
        if not return_dict:
            output = (logits,) + transformer_outputs[1:]
            return ((loss,) + output) if loss is not None else output
        
        return SequenceClassifierOutputWithPast(
            loss=loss,
            logits=logits,
            past_key_values=transformer_outputs.past_key_values,
            hidden_states=transformer_outputs.hidden_states,
            attentions=transformer_outputs.attentions,
        )


class Gemma3TextForSequenceClassification(Gemma3ForSequenceClassification):
    """Gemma3 Text model variant for sequence classification.
    
    This is specifically for text-only Gemma3 models (like 1B variants) that don't
    include multimodal capabilities but still need sequence classification heads.
    """
    
    def __init__(self, config):
        super().__init__(config)
        # Text-only models may have different initialization requirements
        # but the base implementation should work fine


# Register the custom models with transformers AutoModel system
try:
    from transformers import Gemma3Config, Gemma3TextConfig
    
    # Set the appropriate config class on our models to match what we want to register
    Gemma3ForSequenceClassification.config_class = Gemma3Config
    Gemma3TextForSequenceClassification.config_class = Gemma3TextConfig
    
    # Register both variants
    AutoModelForSequenceClassification.register(Gemma3Config, Gemma3ForSequenceClassification)
    AutoModelForSequenceClassification.register(Gemma3TextConfig, Gemma3TextForSequenceClassification)
    
except (ImportError, ValueError) as e:
    # If registration fails, the models will still work but won't be auto-detected
    import warnings
    warnings.warn(f"Could not register Gemma3 sequence classification models: {e}", stacklevel=2)
    pass

# Register both model classes for auto-detection
Gemma3ForSequenceClassification._keys_to_ignore_on_load_missing = ["lm_head.weight"]
Gemma3TextForSequenceClassification._keys_to_ignore_on_load_missing = ["lm_head.weight"]