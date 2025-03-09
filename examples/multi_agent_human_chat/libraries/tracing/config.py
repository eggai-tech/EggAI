from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # OpenTelemetry settings
    service_namespace: str = Field(default="eggai", env="SERVICE_NAMESPACE")
    otel_endpoint: str = Field(default="http://localhost:4318", env="OTEL_ENDPOINT") 
    otel_endpoint_insecure: bool = Field(default=True, env="OTEL_ENDPOINT_INSECURE")
    otel_exporter_otlp_protocol: str = Field(default="http/protobuf", env="OTEL_EXPORTER_OTLP_PROTOCOL")
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    
    # Instrumentation configuration
    disabled_instrumentors: list[str] = Field(default=["langchain"], env="DISABLED_INSTRUMENTORS")
    
    # Sampling rate (1.0 = 100% of traces are sampled)
    sampling_rate: float = Field(default=1.0, env="SAMPLING_RATE")
    
    model_config = SettingsConfigDict(
        env_prefix="TRACING_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()