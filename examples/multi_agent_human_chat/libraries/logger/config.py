from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables at module level
load_dotenv()


class Settings(BaseSettings):
    log_level: str = Field(default="INFO")
    log_format: str = Field(
        default="%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d %(funcName)s %(message)s",
        env="LOG_FORMAT"
    )
    
    # Logging formatter to use (json, standard, colored)
    log_formatter: str = Field(default="colored")
    
    # In which directories to automatically suppress certain loggers
    suppress_loggers: list[str] = Field(
        default=["httpx", "urllib3", "asyncio", "aiokafka"], 
        env="SUPPRESS_LOGGERS"
    )
    
    # Default suppression level (only apply warnings and above for suppressed loggers)
    suppress_level: str = Field(default="WARNING")
    
    model_config = SettingsConfigDict(
        env_prefix="LOGGER_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()