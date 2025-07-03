"""Tests for configuration settings."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from agents.policies.config import Settings as MainSettings
from agents.policies.ingestion.config import Settings as IngestionSettings


class TestMainConfig:
    """Test main configuration settings."""
    
    def test_default_settings(self):
        """Test default configuration values."""
        settings = MainSettings()
        
        assert settings.app_name == "policies_agent"
        assert settings.language_model == "openai/gpt-4o-mini"
        assert settings.cache_enabled is False
        assert settings.embedding_model == "all-MiniLM-L6-v2"
        assert settings.api_port == 8002
        assert settings.api_host == "0.0.0.0"
        assert settings.prometheus_metrics_port == 9093
    
    def test_env_override(self):
        """Test environment variable override."""
        with patch.dict(os.environ, {
            "POLICIES_APP_NAME": "test_agent",
            "POLICIES_EMBEDDING_MODEL": "all-mpnet-base-v2",
            "POLICIES_API_PORT": "8003",
            "POLICIES_CACHE_ENABLED": "true"
        }):
            settings = MainSettings()
            
            assert settings.app_name == "test_agent"
            assert settings.embedding_model == "all-mpnet-base-v2"
            assert settings.api_port == 8003
            assert settings.cache_enabled is True
    
    def test_kafka_settings(self):
        """Test Kafka configuration."""
        with patch.dict(os.environ, {
            "POLICIES_KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
            "POLICIES_KAFKA_TOPIC_PREFIX": "test",
            "POLICIES_KAFKA_REBALANCE_TIMEOUT_MS": "30000"
        }):
            settings = MainSettings()
            
            assert settings.kafka_bootstrap_servers == "kafka:9092"
            assert settings.kafka_topic_prefix == "test"
            assert settings.kafka_rebalance_timeout_ms == 30000
    
    def test_optional_fields(self):
        """Test optional field handling."""
        settings = MainSettings()
        
        assert settings.language_model_api_base is None
        assert settings.max_context_window is None
    
    def test_model_config(self):
        """Test model configuration settings."""
        settings = MainSettings()
        
        # Check that extra fields are ignored
        with patch.dict(os.environ, {"POLICIES_UNKNOWN_FIELD": "value"}):
            settings2 = MainSettings()
            assert not hasattr(settings2, "unknown_field")


class TestIngestionConfig:
    """Test ingestion configuration settings."""
    
    def test_default_settings(self):
        """Test default ingestion configuration values."""
        settings = IngestionSettings()
        
        assert settings.app_name == "policies_document_ingestion"
        assert settings.temporal_server_url == "localhost:7233"
        assert settings.temporal_namespace == "default"
        assert settings.temporal_task_queue == "policy-rag"
        assert settings.vespa_deployment_mode == "production"
        assert settings.vespa_node_count == 3
        assert settings.vespa_artifacts_dir is None
        assert settings.vespa_hosts_config is None
        assert settings.vespa_services_xml is None
    
    def test_vespa_deployment_settings(self):
        """Test Vespa deployment configuration."""
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_DEPLOYMENT_MODE": "local",
            "POLICIES_DOCUMENT_INGESTION_VESPA_NODE_COUNT": "1",
            "POLICIES_DOCUMENT_INGESTION_VESPA_ARTIFACTS_DIR": "/tmp/artifacts",
            "POLICIES_DOCUMENT_INGESTION_VESPA_HOSTS_CONFIG": "/tmp/hosts.json",
            "POLICIES_DOCUMENT_INGESTION_VESPA_SERVICES_XML": "/tmp/services.xml"
        }):
            settings = IngestionSettings()
            
            assert settings.vespa_deployment_mode == "local"
            assert settings.vespa_node_count == 1
            assert settings.vespa_artifacts_dir == Path("/tmp/artifacts")
            assert settings.vespa_hosts_config == Path("/tmp/hosts.json")
            assert settings.vespa_services_xml == Path("/tmp/services.xml")
    
    def test_path_type_conversion(self):
        """Test Path type conversion for optional fields."""
        # Test None handling
        settings = IngestionSettings()
        assert settings.vespa_artifacts_dir is None
        
        # Test Path conversion
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_ARTIFACTS_DIR": "relative/path"
        }):
            settings = IngestionSettings()
            assert isinstance(settings.vespa_artifacts_dir, Path)
            assert str(settings.vespa_artifacts_dir) == "relative/path"
    
    def test_temporal_settings(self):
        """Test Temporal configuration."""
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_TEMPORAL_SERVER_URL": "temporal:7233",
            "POLICIES_DOCUMENT_INGESTION_TEMPORAL_NAMESPACE": "policies",
            "POLICIES_DOCUMENT_INGESTION_TEMPORAL_TASK_QUEUE": "custom-queue"
        }):
            settings = IngestionSettings()
            
            assert settings.temporal_server_url == "temporal:7233"
            assert settings.temporal_namespace == "policies"
            assert settings.temporal_task_queue == "custom-queue"
    
    def test_invalid_node_count(self):
        """Test validation of node count."""
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_NODE_COUNT": "invalid"
        }):
            with pytest.raises(ValidationError):
                IngestionSettings()
    
    def test_env_prefix(self):
        """Test environment variable prefix handling."""
        # Wrong prefix should not override
        with patch.dict(os.environ, {
            "VESPA_NODE_COUNT": "5",  # Wrong prefix
            "POLICIES_VESPA_NODE_COUNT": "5",  # Wrong prefix
            "POLICIES_DOCUMENT_INGESTION_VESPA_NODE_COUNT": "7"  # Correct prefix
        }):
            settings = IngestionSettings()
            assert settings.vespa_node_count == 7


class TestConfigIntegration:
    """Test configuration integration between modules."""
    
    def test_shared_settings(self):
        """Test settings that are shared between configurations."""
        with patch.dict(os.environ, {
            "POLICIES_OTEL_ENDPOINT": "http://otel:4318",
            "POLICIES_DOCUMENT_INGESTION_OTEL_ENDPOINT": "http://otel2:4318"
        }):
            main_settings = MainSettings()
            ingestion_settings = IngestionSettings()
            
            # Each config has its own namespace
            assert main_settings.otel_endpoint == "http://otel:4318"
            assert ingestion_settings.otel_endpoint == "http://otel2:4318"
    
    def test_deployment_mode_validation(self):
        """Test deployment mode values."""
        # Valid modes
        for mode in ["local", "production"]:
            with patch.dict(os.environ, {
                "POLICIES_DOCUMENT_INGESTION_VESPA_DEPLOYMENT_MODE": mode
            }):
                settings = IngestionSettings()
                assert settings.vespa_deployment_mode == mode
    
    def test_settings_mutability(self):
        """Test that settings can be modified after creation."""
        settings = MainSettings()
        original_name = settings.app_name
        
        # Settings are mutable by default in pydantic_settings
        settings.app_name = "changed"
        assert settings.app_name == "changed"
        assert settings.app_name != original_name


class TestConfigurationEdgeCases:
    """Test edge cases and validation for configuration settings."""
    
    def test_invalid_port_number(self):
        """Test validation of port numbers."""
        # Test negative port - Pydantic will coerce to int without validation
        with patch.dict(os.environ, {"POLICIES_API_PORT": "-1"}):
            settings = MainSettings()
            assert settings.api_port == -1  # No validation, accepts negative
        
        # Test port too large - Pydantic will coerce to int without validation
        with patch.dict(os.environ, {"POLICIES_API_PORT": "70000"}):
            settings = MainSettings()
            assert settings.api_port == 70000  # No validation, accepts large port
        
        # Test non-numeric port - This should raise ValidationError
        with patch.dict(os.environ, {"POLICIES_API_PORT": "not-a-number"}):
            with pytest.raises(ValidationError):
                MainSettings()
    
    def test_boolean_parsing(self):
        """Test various boolean value formats."""
        # Test different true values
        for true_value in ["true", "True", "TRUE", "1", "yes", "Yes", "on"]:
            with patch.dict(os.environ, {"POLICIES_CACHE_ENABLED": true_value}):
                settings = MainSettings()
                assert settings.cache_enabled is True
        
        # Test different false values
        for false_value in ["false", "False", "FALSE", "0", "no", "No", "off"]:
            with patch.dict(os.environ, {"POLICIES_CACHE_ENABLED": false_value}):
                settings = MainSettings()
                assert settings.cache_enabled is False
        
        # Test invalid boolean
        with patch.dict(os.environ, {"POLICIES_CACHE_ENABLED": "maybe"}):
            with pytest.raises(ValidationError):
                MainSettings()
    
    def test_path_validation_ingestion(self):
        """Test Path field validation in ingestion settings."""
        # Test valid paths
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_ARTIFACTS_DIR": "/valid/path",
            "POLICIES_DOCUMENT_INGESTION_VESPA_HOSTS_CONFIG": "../relative/path.json",
            "POLICIES_DOCUMENT_INGESTION_VESPA_SERVICES_XML": "~/home/services.xml"
        }):
            settings = IngestionSettings()
            assert settings.vespa_artifacts_dir == Path("/valid/path")
            assert settings.vespa_hosts_config == Path("../relative/path.json")
            assert settings.vespa_services_xml == Path("~/home/services.xml")
        
        # Test empty path strings (should become None)
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_ARTIFACTS_DIR": "",
            "POLICIES_DOCUMENT_INGESTION_VESPA_HOSTS_CONFIG": "",
        }):
            settings = IngestionSettings()
            assert settings.vespa_artifacts_dir is None
            assert settings.vespa_hosts_config is None
    
    def test_url_validation(self):
        """Test URL field validation."""
        # Valid URLs
        valid_urls = [
            "http://localhost:4318",
            "https://telemetry.example.com",
            "http://192.168.1.1:8080",
            "https://otel-collector:4318/v1/traces"
        ]
        
        for url in valid_urls:
            with patch.dict(os.environ, {"POLICIES_OTEL_ENDPOINT": url}):
                settings = MainSettings()
                assert settings.otel_endpoint == url
        
        # Test temporal server URL (not validated as HTTP URL)
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_TEMPORAL_SERVER_URL": "temporal:7233"
        }):
            settings = IngestionSettings()
            assert settings.temporal_server_url == "temporal:7233"
    
    def test_enum_validation(self):
        """Test enum-like field validation."""
        # Valid deployment modes
        for mode in ["local", "production"]:
            with patch.dict(os.environ, {
                "POLICIES_DOCUMENT_INGESTION_VESPA_DEPLOYMENT_MODE": mode
            }):
                settings = IngestionSettings()
                assert settings.vespa_deployment_mode == mode
        
        # Invalid deployment mode - will be accepted as-is (no enum validation)
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_DEPLOYMENT_MODE": "invalid_mode"
        }):
            # No validation, accepts any string
            settings = IngestionSettings()
            assert settings.vespa_deployment_mode == "invalid_mode"
    
    def test_missing_required_fields(self):
        """Test that all fields have defaults (no required fields without defaults)."""
        # Main settings should work without any env vars
        settings = MainSettings()
        assert settings.app_name == "policies_agent"
        
        # Ingestion settings should work without any env vars
        ingestion_settings = IngestionSettings()
        assert ingestion_settings.app_name == "policies_document_ingestion"
    
    def test_integer_bounds(self):
        """Test integer field boundaries."""
        # Test Kafka timeout boundaries
        with patch.dict(os.environ, {"POLICIES_KAFKA_REBALANCE_TIMEOUT_MS": "0"}):
            settings = MainSettings()
            assert settings.kafka_rebalance_timeout_ms == 0
        
        with patch.dict(os.environ, {"POLICIES_KAFKA_REBALANCE_TIMEOUT_MS": "2147483647"}):
            settings = MainSettings()
            assert settings.kafka_rebalance_timeout_ms == 2147483647
        
        # Test node count boundaries - zero should be accepted without validation
        with patch.dict(os.environ, {"POLICIES_DOCUMENT_INGESTION_VESPA_NODE_COUNT": "0"}):
            settings = IngestionSettings()
            assert settings.vespa_node_count == 0  # No validation, accepts 0
    
    def test_special_characters_in_strings(self):
        """Test handling of special characters in string fields."""
        special_strings = [
            "app-name-with-dashes",
            "app_name_with_underscores",
            "app.name.with.dots",
            "app name with spaces",
            "app@name#with$special%chars",
            "日本語",  # Unicode
            "app\nwith\nnewlines",
            "app\twith\ttabs"
        ]
        
        for special_string in special_strings:
            with patch.dict(os.environ, {"POLICIES_APP_NAME": special_string}):
                settings = MainSettings()
                assert settings.app_name == special_string
    
    def test_environment_variable_precedence(self):
        """Test that environment variables override defaults."""
        # Create settings with defaults
        settings1 = MainSettings()
        default_model = settings1.language_model
        
        # Override with environment variable
        with patch.dict(os.environ, {"POLICIES_LANGUAGE_MODEL": "custom/model"}):
            settings2 = MainSettings()
            assert settings2.language_model == "custom/model"
            assert settings2.language_model != default_model
    
    def test_empty_string_handling(self):
        """Test how empty strings are handled for different field types."""
        # Empty string for string field - env_ignore_empty=True means it uses default
        with patch.dict(os.environ, {"POLICIES_KAFKA_TOPIC_PREFIX": ""}):
            settings = MainSettings()
            assert settings.kafka_topic_prefix == "eggai"  # Uses default due to env_ignore_empty
        
        # Empty string for optional Path field - also ignored, uses None default
        with patch.dict(os.environ, {
            "POLICIES_DOCUMENT_INGESTION_VESPA_ARTIFACTS_DIR": ""
        }):
            settings = IngestionSettings()
            # Empty string is ignored, uses None default
            assert settings.vespa_artifacts_dir is None
    
    def test_whitespace_handling(self):
        """Test handling of whitespace in configuration values."""
        # Leading/trailing whitespace should be preserved for strings
        with patch.dict(os.environ, {"POLICIES_APP_NAME": "  spaced  "}):
            settings = MainSettings()
            assert settings.app_name == "  spaced  "
        
        # Whitespace in numbers - Pydantic will strip and parse
        with patch.dict(os.environ, {"POLICIES_API_PORT": " 8080 "}):
            settings = MainSettings()
            assert settings.api_port == 8080  # Pydantic strips whitespace and parses
    
    def test_case_sensitivity(self):
        """Test case sensitivity of environment variables."""
        # Environment variable names are case-sensitive
        with patch.dict(os.environ, {
            "policies_app_name": "lowercase",
            "POLICIES_APP_NAME": "uppercase"
        }):
            settings = MainSettings()
            assert settings.app_name == "uppercase"  # Should use uppercase version
    
    def test_null_and_none_handling(self):
        """Test handling of null/None values."""
        # String "None" should be treated as a string
        with patch.dict(os.environ, {"POLICIES_APP_NAME": "None"}):
            settings = MainSettings()
            assert settings.app_name == "None"
        
        # String "null" should be treated as a string
        with patch.dict(os.environ, {"POLICIES_KAFKA_TOPIC_PREFIX": "null"}):
            settings = MainSettings()
            assert settings.kafka_topic_prefix == "null"
    
    def test_very_long_values(self):
        """Test handling of very long configuration values."""
        # Very long string
        long_string = "a" * 10000
        with patch.dict(os.environ, {"POLICIES_APP_NAME": long_string}):
            settings = MainSettings()
            assert settings.app_name == long_string
            assert len(settings.app_name) == 10000
    
    def test_concurrent_settings_creation(self):
        """Test that multiple settings instances don't interfere."""
        # Create multiple settings instances with different env vars
        with patch.dict(os.environ, {"POLICIES_APP_NAME": "instance1"}):
            settings1 = MainSettings()
        
        with patch.dict(os.environ, {"POLICIES_APP_NAME": "instance2"}):
            settings2 = MainSettings()
        
        # Each should have its own values
        assert settings1.app_name == "instance1"
        assert settings2.app_name == "instance2"