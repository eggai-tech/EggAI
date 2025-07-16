"""
Root-level pytest configuration with common fixtures.

This file provides shared fixtures used across all tests in the project.
"""

import asyncio
from typing import AsyncGenerator, Generator

import mlflow
import pytest
from dspy import LM
from mlflow.exceptions import RestException


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def mock_language_model(monkeypatch) -> None:
    """Mock the language model for testing without API calls."""
    class MockLM(LM):
        def __init__(self, model: str):
            self.model = model
            self.history = []
            self.kwargs = {"temperature": 0.7}
            
        def __call__(self, prompt=None, messages=None, **kwargs):
            return ["Mocked response for testing"]
    
    monkeypatch.setattr("dspy.LM", MockLM)


@pytest.fixture
async def mock_publish_channel(monkeypatch) -> AsyncGenerator[list, None]:
    """Mock channel publish method to capture published messages."""
    published_messages = []
    
    async def mock_publish(self, message):
        published_messages.append(message)
    
    monkeypatch.setattr("eggai.Channel.publish", mock_publish)
    yield published_messages
    published_messages.clear()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "requires_mlflow_models: mark test as requiring MLflow models (skipped if models are missing)"
    )


def check_mlflow_model_exists(model_name: str, version: str) -> bool:
    """Check if an MLflow model exists."""
    try:
        client = mlflow.MlflowClient()
        client.get_model_version(name=model_name, version=version)
        return True
    except (RestException, Exception):
        return False


def pytest_collection_modifyitems(config, items):
    """Skip tests that require MLflow models if the models are not available."""
    skip_mlflow = pytest.mark.skip(reason="Required MLflow models not available")
    
    # Check if specific models exist
    v3_model_exists = check_mlflow_model_exists("fewshot_baseline_n_all", "15")
    v5_model_exists = check_mlflow_model_exists("attention_net_0.25_0.0002", "1")
    
    for item in items:
        # Skip classifier v3 tests if model is missing
        if "test_classifier_v3" in item.nodeid and not v3_model_exists:
            item.add_marker(skip_mlflow)
        
        # Skip classifier v5 tests if model is missing
        if "test_classifier_v5" in item.nodeid and not v5_model_exists:
            item.add_marker(skip_mlflow)
        
        # Also check for the marker
        if "requires_mlflow_models" in item.keywords:
            if not (v3_model_exists and v5_model_exists):
                item.add_marker(skip_mlflow)