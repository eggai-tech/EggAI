import datetime
import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class AttentionNetSettings(BaseSettings):
    # Model configuration
    n_classes: int = Field(default=5)
    model_name_template: str = Field(default="attention_net_{dropout_rate}_{learning_rate}")
    embedding_dim: int = Field(default=384)
    hidden_dims: tuple[int, int] = Field(default=(256, 128))
    dropout_rate: float = Field(default=0.25)

    # Train/test dataset configuration
    train_dataset_path: str = Field(
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data_sets/triage-training-proofread.jsonl",
        ),
        env="TRAIN_DATASET_PATH",
    )
    test_dataset_path: str = Field(
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data_sets/triage-testing-proofread.jsonl",
        ),
        env="TEST_DATASET_PATH",
    )

    # Training configuration
    device: str = Field(default="")
    max_num_epochs: int = Field(default=250)
    # number of warmup epochs for the learning rate scheduler
    num_warmup_steps: int = Field(default=5)
    # betas for the AdamW optimizer
    betas: tuple[float, float] = Field(default=(0.9, 0.999))
    weight_decay: float = Field(default=1e-2)
    learning_rate: float = Field(default=2e-4)
    # number of epochs with no improvement after which training will be stopped
    patience: int = Field(default=5)
    checkpoint_dir: str = Field(default="checkpoints")

    # MLflow configuration
    mlflow_tracking_uri: str = Field(default="http://127.0.0.1:5001")
    mlflow_experiment_name: str = Field(default="triage-attention-net-training")

    @property
    def model_config_dict(self):
        return {
            "n_classes": self.n_classes,
            "embedding_dim": self.embedding_dim,
            "hidden_dims": self.hidden_dims,
            "dropout": self.dropout_rate,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "train_dataset_path": self.train_dataset_path,
            "test_dataset_path": self.test_dataset_path,
        }

    def generate_run_name(self):
        """Generate a dynamic run name with timestamp and metadata."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"attention_net_{self.dropout_rate}_{self.learning_rate}_{timestamp}"

    @property
    def mlflow_config_dict(self):
        run_name = self.generate_run_name()
        return {
            "tracking_uri": self.mlflow_tracking_uri,
            "experiment_name": self.mlflow_experiment_name,
            "run_name": run_name,
        }

    model_config = SettingsConfigDict(
        env_prefix="ATTENTION_NET_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        protected_namespaces=('settings_',)  # Fix for model_name_template warning
    )


settings = AttentionNetSettings()
