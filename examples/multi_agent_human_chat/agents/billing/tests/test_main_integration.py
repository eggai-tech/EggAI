"""Integration tests for Billing main module"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Mock dependencies before import
with patch('agents.billing.main.create_kafka_transport'):
    with patch('agents.billing.main.eggai_set_default_transport'):
        with patch('agents.billing.main.billing_agent') as mock_agent:
            # Setup mock agent
            mock_agent.start = AsyncMock()
            mock_agent.stop = MagicMock()
            
            with patch('agents.billing.main.init_telemetry'):
                with patch('agents.billing.main.dspy_set_language_model'):
                    from agents.billing.main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


def test_health_endpoint(client):
    """Test that health endpoint is available"""
    response = client.get("/health")
    assert response.status_code == 200


def test_billing_list_endpoint(client):
    """Test that billing list endpoint is available"""
    response = client.get("/api/v1/billing?limit=5")
    assert response.status_code == 200


def test_billing_stats_endpoint(client):
    """Test that billing stats endpoint is available"""
    response = client.get("/api/v1/billing/stats")
    assert response.status_code == 200


def test_app_has_cors_middleware(client):
    """Test that CORS middleware is configured"""
    # Make a preflight request
    response = client.options(
        "/api/v1/billing",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET"
        }
    )
    # Check CORS headers
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"