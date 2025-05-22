from dataclasses import dataclass
from time import perf_counter

import numpy as np
import torch
from dotenv import load_dotenv

from agents.triage.attention_net.attention_based_classifier import AttentionBasedClassifier, \
    AttentionBasedClassifierWrapper
from agents.triage.attention_net.config import AttentionNetSettings
from agents.triage.config import Settings
from agents.triage.models import ClassifierMetrics, TargetAgent
from libraries.mlflow_utils import find_model

load_dotenv()
settings = Settings()
nn_settings = AttentionNetSettings()

checkpoint_path = find_model(settings.classifier_v5_model_name, version=settings.classifier_v5_model_version)
state_dict = torch.load(checkpoint_path, map_location="cpu")
attention_net = AttentionBasedClassifier(
    embedding_dim=nn_settings.embedding_dim,
    hidden_dims=nn_settings.hidden_dims,
    n_classes=nn_settings.n_classes,
    dropout=nn_settings.dropout_rate
)
attention_net.load_state_dict(state_dict)
attention_net.eval()
device = settings.classifier_v5_device
if not device:
    device = "cuda" if torch.cuda.is_available() else "cpu"
# create wrapper
model = AttentionBasedClassifierWrapper(attention_net, device=device)


@dataclass
class ClassificationResult:
    target_agent: TargetAgent
    metrics: ClassifierMetrics


def classifier_v5(chat_history: str) -> ClassificationResult:
    labels = {
        TargetAgent.BillingAgent: 0,
        TargetAgent.PolicyAgent: 1,
        TargetAgent.ClaimsAgent: 2,
        TargetAgent.EscalationAgent: 3,
        TargetAgent.ChattyAgent: 4
    }

    time_start = perf_counter()
    prediction_matrix = model.predict_probab([chat_history], return_logits=False)[0]
    best_label = np.argmax(prediction_matrix)
    best_target_agent = [k for k, v in labels.items() if v == best_label][0]
    latency_ms = (perf_counter() - time_start) * 1000

    return ClassificationResult(
        target_agent=best_target_agent,
        metrics=ClassifierMetrics(
            total_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency_ms,
        )
    )


if __name__ == "__main__":
    result = classifier_v5(chat_history="User: I want to know my policy due date.")
    print(result.target_agent)
    print(result.metrics)
