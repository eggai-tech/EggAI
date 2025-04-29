from pathlib import Path
import os
import mlflow
import dotenv
import pickle

from mlflow.types import Schema, ColSpec, DataType
from mlflow.models.signature import ModelSignature
from mlflow.types.schema import Array

from agents.triage.models import TargetAgent

dotenv.load_dotenv()

# Your environment variable printing code remains unchanged
for key, value in sorted(os.environ.items()):
    if key.startswith("AWS") or key.startswith("MLFLOW"):
        print(f"{key}: {value}")

if __name__ == "__main__":
    checkpoint_dir = Path("baseline_checkpoints")
    for pickle_file in checkpoint_dir.glob("*.pkl"):
        print(f"Loading checkpoint: {pickle_file}")
        with open(pickle_file, "rb") as f:
            current_classifier = pickle.load(f)
            classifier = current_classifier[0]
            class_indices = classifier.classes_
            n_classes = len(class_indices)

            # Specify that 'text' is now an array of strings
            input_schema = Schema([
                ColSpec(type=Array(DataType.string), name="text")
            ])

            # Specify that each agent column is an array of doubles
            target_agent_names = [agent.name for agent in [
                TargetAgent.BillingAgent,
                TargetAgent.PolicyAgent,
                TargetAgent.ClaimsAgent,
                TargetAgent.EscalationAgent,
                TargetAgent.ChattyAgent
            ]]
            output_schema = Schema([
                ColSpec(type=Array(DataType.double), name=agent_name)
                for agent_name in target_agent_names
            ])

            signature = ModelSignature(
                inputs=input_schema,
                outputs=output_schema
            )

            # Now input_example is a batch of 2 conversations
            input_example = {
                "text": [
                    "User: Hello, I need help with insurance policy.",
                    "User: What’s my claim status?"
                ]
            }

            # Validate the input example (optional but recommended)
            try:
                mlflow.models.validate_serving_input(model_uri=pickle_file.stem, input_example=input_example)
            except Exception as e:
                print(f"Error validating serving input: {e}")

            mlflow.sklearn.log_model(
                sk_model=classifier,
                artifact_path="model",
                registered_model_name=pickle_file.stem,
                signature=signature,
                input_example=input_example
            )

    print("All models registered in MLflow Model Registry")
