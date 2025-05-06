from pydantic_settings import BaseSettings

class WebServerConfig(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/triage_db"
    SECRET_KEY: str = "development_secret_key"
    MODEL: str = "openai/gpt-4o-mini"
    DEBUG: bool = True
    
    class Config:
        env_prefix = ""
