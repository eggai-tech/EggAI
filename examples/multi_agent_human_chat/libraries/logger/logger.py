import logging
import logging.config
import sys
from typing import Optional, Dict, Any

from colorlog import ColoredFormatter

from libraries.logger.config import settings

# Create a default logging configuration dictionary
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": settings.log_format,
        },
        "standard": {
            "format": settings.log_format,
        },
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "datefmt": "%H:%M:%S",
            "log_colors": {
                "DEBUG": "white",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        },
    },
    "handlers": {
        "default": {
            "level": settings.log_level,
            "formatter": settings.log_formatter,
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {  # Root logger
            "level": settings.log_level,
            "handlers": ["default"],
            "propagate": True,
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO", 
            "handlers": ["default"],
            "propagate": False,
        },
    },
}

# Add suppressed loggers
for logger_name in settings.suppress_loggers:
    LOGGING_CONFIG["loggers"][logger_name] = {
        "level": settings.suppress_level,
        "handlers": ["default"],
        "propagate": False,
    }


def configure_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Configure logging based on provided configuration or default settings.
    
    Args:
        config: Optional custom logging configuration dictionary
    """
    logging_config = config or LOGGING_CONFIG
    logging.config.dictConfig(logging_config)


def get_logger(service_name: str) -> logging.Logger:
    """
    Get a configured logger for the specified service.
    
    Args:
        service_name: The name of the service or module requiring logging
        
    Returns:
        A configured logger instance
    """
    configure_logging()
    return logging.getLogger(service_name)


def get_console_logger(service_name: str) -> logging.Logger:
    """
    Get a colorized console logger for the specified service.
    This is particularly useful for development and debugging.
    
    Args:
        service_name: The name of the service or module requiring logging
        
    Returns:
        A configured logger with colorized console output
    """
    logger = logging.getLogger(service_name)
    
    # Return the logger if handlers are already configured
    if logger.handlers:
        return logger
    
    # Clear existing handlers if any
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    log_colors = {
        "DEBUG": "white",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }

    console_formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        log_colors=log_colors,
    )

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(settings.log_level)
    console_handler.setFormatter(console_formatter)

    # Suppress noisy loggers
    for logger_name in settings.suppress_loggers:
        logging.getLogger(logger_name).setLevel(settings.suppress_level)

    logger.setLevel(settings.log_level)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger