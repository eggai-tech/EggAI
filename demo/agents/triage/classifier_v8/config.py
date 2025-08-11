from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClassifierV8Settings(BaseSettings):
    n_classes: int = Field(default=5)
    model_config = SettingsConfigDict(
        env_prefix="TRIAGE_V8_",
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
        protected_namespaces=('settings_',)
    )
    
    # RoBERTa model configuration
    model_name: str = Field(default="roberta-base", description="RoBERTa base model from HuggingFace")

    # Specify device for model loading
    device: str = Field(default="mps", description="Device to load the model on (mps, cuda, cpu)")
    
    # Fine-tuning parameters
    train_sample_size: int = Field(default=-1, description="Number of training samples to use")
    eval_sample_size: int = Field(default=-1, description="Number of evaluation samples to use")
    learning_rate: float = Field(default=2e-4)
    num_epochs: int = Field(default=10)
    batch_size: int = Field(default=8)
    gradient_accumulation_steps: int = Field(default=2)

    # LoRA parameters
    lora_r: int = Field(default=16)
    lora_alpha: int = Field(default=32)
    lora_dropout: float = Field(default=0.1)
    lora_target_modules: list = Field(default_factory=lambda: ["query", "value"])
    
    # Model paths
    output_dir: str = Field(default="./models/roberta-triage-v8")