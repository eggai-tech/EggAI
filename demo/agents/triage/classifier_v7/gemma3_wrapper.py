from typing import Optional

import torch
from torch import nn
from transformers import (
    AutoModelForSequenceClassification,
    Cache,
    Gemma3PreTrainedModel,
    Gemma3TextConfig,
    Gemma3TextModel,
)
from transformers.modeling_outputs import SequenceClassifierOutputWithPast


def _compute_loss(logits: torch.Tensor, labels: torch.Tensor, num_labels: int):
    if labels is None:
        return None

    # we only deal with single label classification here
    if num_labels == 1:
        # BCE loss
        loss_fct = nn.BCEWithLogitsLoss()
        return loss_fct(logits, labels.float())
    else:
        # Cross entropy loss
        loss_fct = nn.CrossEntropyLoss()
        return loss_fct(logits.view(-1, num_labels), labels.view(-1))


class Gemma3TextForSequenceClassification(Gemma3PreTrainedModel):
    """
    Gemma3 model with sequence classification head on top (just a linear layer on top of the pooled output)
    """
    config_class = Gemma3TextConfig

    def __init__(self, config: Gemma3TextConfig):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.model = Gemma3TextModel(config)
        # add dropout to slow down overfitting
        self.dropout = nn.Dropout(config.hidden_dropout if hasattr(config, "hidden_dropout") else 0.1)
        self.classifier = nn.Linear(config.hidden_size, config.num_labels)
        # Initialize weights and apply final processing
        self.post_init()

    def forward(
            self,
            input_ids: Optional[torch.LongTensor] = None,
            attention_mask: Optional[torch.Tensor] = None,
            position_ids: Optional[torch.LongTensor] = None,
            past_key_values: Optional[Cache] = None,
            labels: Optional[torch.Tensor] = None,
            inputs_embeds: Optional[torch.FloatTensor] = None,
            use_cache: Optional[bool] = None,
            output_attentions: Optional[bool] = None,
            output_hidden_states: Optional[bool] = None,
            cache_position: Optional[torch.LongTensor] = None,
            return_dict: Optional[bool] = None,
    ) -> SequenceClassifierOutputWithPast:
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_values=past_key_values,
            inputs_embeds=inputs_embeds,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            cache_position=cache_position,
            return_dict=return_dict
        )
        pooled_output = outputs.last_hidden_state[:, 0]  # use first token (similar to [CLS])
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        loss = _compute_loss(logits, labels, self.num_labels)

        if not return_dict:
            out = (logits,) + outputs[1:]
            return ((loss,) + out) if loss is not None else out

        return SequenceClassifierOutputWithPast(
            loss=loss,
            logits=logits,
            past_key_values=outputs.past_key_values,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions
        )


# register for auto-loading
AutoModelForSequenceClassification.register(
    Gemma3TextConfig, Gemma3TextForSequenceClassification
)
