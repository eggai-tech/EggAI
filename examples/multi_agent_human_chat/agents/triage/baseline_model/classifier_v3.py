from dataclasses import dataclass

import numpy as np
from dotenv import load_dotenv

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.config import Settings
from agents.triage.mlflow_experiments.utils import find_model
from agents.triage.models import TargetAgent

load_dotenv()
settings = Settings()

few_shots_classifier = FewShotsClassifier()
few_shots_classifier.load(find_model(settings.classifier_v4_model_name, version=settings.classifier_v4_model_version))

@dataclass
class ClassificationResult:
    target_agent: TargetAgent

def classifier_v3(chat_history: str) -> ClassificationResult:
    labels = {
        TargetAgent.BillingAgent: 0,
        TargetAgent.PolicyAgent: 1,
        TargetAgent.ClaimsAgent: 2,
        TargetAgent.EscalationAgent: 3,
        TargetAgent.ChattyAgent: 4
    }
    prediction_matrix = few_shots_classifier([chat_history])[0]

    best_label = np.argmax(prediction_matrix)
    best_target_agent = [k for k, v in labels.items() if v == best_label][0]
    
    return ClassificationResult(target_agent=best_target_agent)
    
if __name__ == "__main__":
    result = classifier_v3(chat_history="User: I want to talk with manager, im so angry.")
    print(result.target_agent)