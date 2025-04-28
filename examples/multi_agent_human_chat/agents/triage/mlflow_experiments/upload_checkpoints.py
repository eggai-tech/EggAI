import os
from pathlib import Path

import mlflow
import dotenv
import pickle

from agents.triage.models import TargetAgent

dotenv.load_dotenv()

for key, value in sorted(os.environ.items()):
    if key.startswith("AWS") or key.startswith("MLFLOW"):
        print(f"{key}: {value}")

if __name__ == "__main__":
    checkpoint_dir = Path("baseline_checkpoints")
    for pickle_file in checkpoint_dir.glob("*.pkl"):
        print(f"Loading checkpoint: {pickle_file}")
        with open(pickle_file, "rb") as f:
            current_classifier = pickle.load(f)

            input_schema = mlflow.types.Schema([
                mlflow.types.ColSpec(type="string", name="text")
            ])

            classifier = current_classifier[0]
            class_indices = classifier.classes_
            n_classes = len(class_indices)

            target_agent_values = [
                TargetAgent.BillingAgent,
                TargetAgent.PolicyAgent,
                TargetAgent.ClaimsAgent,
                TargetAgent.EscalationAgent,
                TargetAgent.ChattyAgent
            ]

            output_schema = mlflow.types.Schema([
                mlflow.types.ColSpec(type="double", name=agent_value)
                for agent_value in target_agent_values
            ])

            signature = mlflow.models.ModelSignature(inputs=input_schema, outputs=output_schema)

            input_example = {"text": "User: Hello, I need help with insurance policy."}

            mlflow.sklearn.log_model(
                sk_model=classifier,
                artifact_path="model",
                registered_model_name=pickle_file.stem,
                signature=signature,
                input_example=input_example
            )

    print("All models registered in MLflow Model Registry")