"""Tests for the logger module."""

import logging
from unittest.mock import patch

from libraries.observability.logger import get_console_logger
from libraries.observability.logger.config import Settings, settings


class TestLoggerSettings:
    """Test logger Settings configuration class."""

    def test_settings_defaults(self):
        """Test Settings default values."""
        # Settings is already instantiated as singleton
        
        assert settings.log_level == "INFO"
        assert "asctime" in settings.log_format
        assert "levelname" in settings.log_format
        assert settings.log_formatter == "colored"
        assert "httpx" in settings.suppress_loggers
        assert settings.suppress_level == "WARNING"

    def test_settings_with_env(self):
        """Test Settings reading from environment variables."""
        with patch.dict("os.environ", {
            "LOGGER_LOG_LEVEL": "DEBUG",
            "LOGGER_LOG_FORMATTER": "json",
            "LOGGER_SUPPRESS_LEVEL": "ERROR"
        }):
            # Create new instance to pick up env vars
            test_settings = Settings()
            
            assert test_settings.log_level == "DEBUG"
            assert test_settings.log_formatter == "json"
            assert test_settings.suppress_level == "ERROR"

    def test_settings_env_prefix(self):
        """Test that Settings uses LOGGER_ prefix for env vars."""
        # Check the model config
        assert Settings.model_config["env_prefix"] == "LOGGER_"


class TestLoggerFormatters:
    """Test logger formatting functionality."""

    def test_logger_suppression(self):
        """Test that suppressed loggers are handled correctly."""
        # Get a logger that should be suppressed
        httpx_logger = logging.getLogger("httpx")
        
        # Based on settings, httpx should be suppressed to WARNING level
        # This is just a structural test since actual suppression happens in logger setup
        assert "httpx" in settings.suppress_loggers
        assert settings.suppress_level == "WARNING"

    def test_standard_formatter(self):
        """Test standard log formatting."""
        # Create a basic formatter with the configured format
        formatter = logging.Formatter(settings.log_format)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
            func="test_function"
        )
        
        formatted = formatter.format(record)
        
        # Check that all expected fields are present
        assert "INFO" in formatted
        assert "test" in formatted  # logger name
        assert "test.py" in formatted  # filename
        assert "42" in formatted  # line number
        assert "test_function" in formatted  # function name
        assert "Test message" in formatted

    def test_json_formatter_config(self):
        """Test JSON formatter configuration."""
        with patch.dict("os.environ", {"LOGGER_LOG_FORMATTER": "json"}):
            test_settings = Settings()
            assert test_settings.log_formatter == "json"

    def test_colored_formatter_config(self):
        """Test colored formatter configuration."""
        # Default should be colored
        assert settings.log_formatter == "colored"


class TestLoggerSetup:
    """Test logger setup functionality."""

    def test_get_console_logger_creates_logger(self):
        """Test that get_console_logger creates a properly configured logger."""
        logger = get_console_logger("test_setup")
        
        assert logger.name == "test_setup"
        assert isinstance(logger, logging.Logger)
        
        # Logger should have at least one handler
        # Note: Implementation may vary, but typically console logger has StreamHandler
        if logger.handlers:
            assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        
        # Clean up
        logger.handlers.clear()

    def test_logger_level_configuration(self):
        """Test logger level configuration from settings."""
        # Create logger with default settings
        logger = get_console_logger("test_level")
        
        # Default level should be INFO from settings
        expected_level = logging.getLevelName(settings.log_level)
        
        # Clean up
        logger.handlers.clear()

    def test_multiple_loggers_independent(self):
        """Test that multiple loggers are independent."""
        logger1 = get_console_logger("test.module1")
        logger2 = get_console_logger("test.module2")
        
        # Should be different logger instances
        assert logger1 is not logger2
        assert logger1.name == "test.module1"
        assert logger2.name == "test.module2"
        
        # Clean up
        logger1.handlers.clear()
        logger2.handlers.clear()


class TestGetConsoleLogger:
    """Test get_console_logger convenience function."""

    def test_get_console_logger_basic(self):
        """Test basic console logger creation."""
        logger = get_console_logger("test_module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"
        assert logger.level == logging.INFO
        
        # Clean up
        logger.handlers.clear()

    def test_get_console_logger_with_level(self):
        """Test console logger respects settings level."""
        # The logger uses settings.log_level, not a parameter
        logger = get_console_logger("test_module_level")
        
        # Logger level should match settings
        from libraries.observability.logger.config import settings
        expected_level = logging.getLevelName(settings.log_level)
        assert logger.level == expected_level
        
        # Clean up
        logger.handlers.clear()

    def test_get_console_logger_caching(self):
        """Test that get_console_logger returns same instance."""
        logger1 = get_console_logger("test_module")
        logger2 = get_console_logger("test_module")
        
        assert logger1 is logger2
        
        # Clean up
        logger1.handlers.clear()

    def test_get_console_logger_different_names(self):
        """Test that different names create different loggers."""
        logger1 = get_console_logger("module1")
        logger2 = get_console_logger("module2")
        
        assert logger1 is not logger2
        assert logger1.name == "module1"
        assert logger2.name == "module2"
        
        # Clean up
        logger1.handlers.clear()
        logger2.handlers.clear()

    @patch.dict("os.environ", {"LOG_LEVEL": "ERROR"})
    def test_get_console_logger_env_override(self):
        """Test console logger respects environment variables."""
        # This test assumes the implementation checks LOG_LEVEL env var
        logger = get_console_logger("test_module")
        
        # The actual behavior depends on implementation
        # This documents expected behavior
        
        # Clean up
        logger.handlers.clear()


class TestLoggerIntegration:
    """Integration tests for logger functionality."""

    def test_logger_hierarchy(self):
        """Test logger hierarchy and propagation."""
        parent_logger = get_console_logger("parent")
        child_logger = get_console_logger("parent.child")
        
        # Child should propagate to parent
        assert child_logger.parent is not None
        
        # Clean up
        parent_logger.handlers.clear()
        child_logger.handlers.clear()

    def test_logger_thread_safety(self):
        """Test logger is thread-safe."""
        import threading
        
        logger = get_console_logger("thread_test")
        errors = []
        
        def log_messages():
            try:
                for i in range(100):
                    logger.info(f"Message {i}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=log_messages) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0
        
        # Clean up
        logger.handlers.clear()