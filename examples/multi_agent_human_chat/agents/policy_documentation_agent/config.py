"""Configuration settings for the Policy Documentation Agent."""

from pydantic import BaseSettings


class PolicyDocumentationAgentSettings(BaseSettings):
    """Settings for the Policy Documentation Agent."""
    
    # Agent identification
    agent_name: str = "PolicyDocumentationAgent"
    app_name: str = "policy_documentation_agent"
    
    # Model configuration
    model_provider: str = "openai"
    model_name: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 2000
    
    # RAG configuration
    max_documents_per_query: int = 5
    max_context_length: int = 4000
    retrieval_threshold: float = 0.5
    
    # Index configuration
    index_name: str = "policies_index"
    embedding_model: str = "colbert-ir/colbertv2.0"
    
    # Timeout settings
    default_timeout_seconds: float = 30.0
    retrieval_timeout_seconds: float = 30.0
    augmentation_timeout_seconds: float = 30.0
    generation_timeout_seconds: float = 60.0
    
    # Logging configuration
    log_level: str = "INFO"
    enable_tracing: bool = True
    
    class Config:
        env_prefix = "POLICY_DOC_AGENT_"
        case_sensitive = False


# Global settings instance
settings = PolicyDocumentationAgentSettings()