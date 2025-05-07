from typing import List, Optional, Union
import os
import datetime

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class FewshotSettings(BaseSettings):
    # Model configuration
    n_classes: int = Field(default=5)
    n_examples: Optional[int] = Field(default=None)
    seed: Union[int, List[int]] = Field(default=[42, 47, 53])
    model_name_template: str = Field(default="fewshot_baseline_n_{n_examples}")

    # Dataset configuration
    train_dataset_paths: List[str] = Field(
        default_factory=lambda: [
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data_sets/triage-training-proofread.jsonl",
            )
        ],
        env="TRAIN_DATASET_PATHS",
    )

    # MLflow configuration
    mlflow_tracking_uri: str = Field(default="http://127.0.0.1:5001")
    mlflow_experiment_name: str = Field(default="triage-model-training")
    mlflow_run_name: Optional[str] = Field(default=None)

    # For evaluation
    test_dataset_path: str = Field(
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data_sets/triage-testing.jsonl",
        ),
        env="TEST_DATASET_PATH",
    )

    @property
    def model_config_dict(self):
        return {
            "n_classes": self.n_classes,
            "n_examples": self.n_examples,
            "seed": self.seed,
            "name": self.model_name_template,
        }

    @property
    def dataset_config_dict(self):
        return {"paths": self.dataset_paths}

    def generate_run_name(self):
        """Generate a dynamic run name with timestamp and metadata."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.n_examples is None:
            n_examples_str = "all"
        else:
            n_examples_str = str(self.n_examples)

        return f"fewshot_baseline_n_{n_examples_str}_{timestamp}"

    @property
    def mlflow_config_dict(self):
        run_name = self.mlflow_run_name or self.generate_run_name()
        return {
            "tracking_uri": self.mlflow_tracking_uri,
            "experiment_name": self.mlflow_experiment_name,
            "run_name": run_name,
        }

    @property
    def eval_config_dict(self):
        return {
            "model": {
                "n_classes": self.n_classes,
                "path": self.model_path,
                "artifact_uri": self.model_artifact_uri,
            },
            "dataset": {"path": self.eval_dataset_path},
            "mlflow": self.mlflow_config_dict,
        }

    model_config = SettingsConfigDict(
        env_prefix="FEWSHOT_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = FewshotSettings()
