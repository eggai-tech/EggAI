from dataclasses import dataclass
from time import perf_counter

import numpy as np
from dotenv import load_dotenv

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.config import Settings
from agents.triage.models import TargetAgent
from libraries.mlflow_utils import find_model

load_dotenv()
settings = Settings()

few_shots_classifier = FewShotsClassifier.load(find_model(settings.classifier_v3_model_name, version=settings.classifier_v3_model_version))

@dataclass
class ClassificationResult:
    target_agent: TargetAgent
    metrics: dict = None

def classifier_v3(chat_history: str) -> ClassificationResult:
    labels = {
        TargetAgent.BillingAgent: 0,
        TargetAgent.PolicyAgent: 1,
        TargetAgent.ClaimsAgent: 2,
        TargetAgent.EscalationAgent: 3,
        TargetAgent.ChattyAgent: 4
    }
    #
    # # get last line from chat history
    # chat_history = chat_history.strip()
    # if chat_history.count("\n") > 0:
    #     chat_history = chat_history.split("\n")[-1]

    time_start = perf_counter()
    prediction_matrix = few_shots_classifier([chat_history])[0]
    best_label = np.argmax(prediction_matrix)
    best_target_agent = [k for k, v in labels.items() if v == best_label][0]
    latency_ms = (perf_counter() - time_start) * 1000

    metrics = {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_ms": latency_ms,
    }
    
    return ClassificationResult(
        target_agent=best_target_agent,
        metrics=metrics
    )
    
if __name__ == "__main__":
    result = classifier_v3(chat_history="User: I want to know my policy due date.")
    print(result.target_agent)
    print(result.metrics)