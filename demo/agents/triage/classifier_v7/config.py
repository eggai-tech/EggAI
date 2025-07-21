from pydantic import Field
from pydantic_settings import BaseSettings


class ClassifierV7Settings(BaseSettings):
    """Configuration for Classifier V7 (Gemma3 via HuggingFace)"""
    
    # HuggingFace Gemma model configuration  
    model_name: str = Field(default="google/gemma-3-1b-it", description="Gemma 3 model from HuggingFace")
    use_qat_model: bool = Field(default=False, description="Use QAT (Quantized Aware Training) model if available")
    use_4bit: bool = Field(default=False, description="Use 4-bit quantization for non-QAT models (disabled by default for compatibility)")
    use_lora: bool = Field(default=True, description="Use LoRA for fine-tuning")
    
    # Fine-tuning parameters
    learning_rate: float = Field(default=2e-4)
    num_epochs: int = Field(default=3)
    batch_size: int = Field(default=1)
    gradient_accumulation_steps: int = Field(default=4)
    max_length: int = Field(default=512)
    
    # LoRA parameters
    lora_r: int = Field(default=16)
    lora_alpha: int = Field(default=16)
    lora_dropout: float = Field(default=0.05)
    
    # Model paths  
    output_dir: str = Field(default="./models/gemma3-triage-v7")
    
    def get_model_name(self) -> str:
        """Get the appropriate model name based on QAT preference"""
        if self.use_qat_model:
            # Map base models to their QAT variants
            qat_mapping = {
                # Gemma 3 models (newer)
                "google/gemma-3-1b-it": "google/gemma-3-qat-1b-it", 
                "google/gemma-3-2b-it": "google/gemma-3-qat-2b-it",
                "google/gemma-3-9b-it": "google/gemma-3-qat-9b-it",
                "google/gemma-3-27b-it": "google/gemma-3-qat-27b-it",
                # Gemma 2 models (better compatibility)
                "google/gemma-2-2b-it": "google/gemma-2-2b-it",  # No QAT variant yet
                "google/gemma-2-9b-it": "google/gemma-2-9b-it",
                "google/gemma-2-27b-it": "google/gemma-2-27b-it"
            }
            return qat_mapping.get(self.model_name, self.model_name)
        return self.model_name
    
    class Config:
        env_prefix = "TRIAGE_V7_"
        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables