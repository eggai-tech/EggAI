"""Tests for policies API routes"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.policies.agent.api.routes import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/api/v1")


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "policies-agent"


def test_list_personal_policies(client):
    """Test listing personal policies"""
    response = client.get("/api/v1/policies?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "policies" in data
    assert "total" in data
    assert isinstance(data["policies"], list)


def test_list_policies_with_category_filter(client):
    """Test listing policies with category filter"""
    response = client.get("/api/v1/policies?category=auto&limit=10")
    assert response.status_code == 200
    data = response.json()
    # All returned policies should be auto category
    for policy in data["policies"]:
        assert policy["policy_category"] == "auto"


def test_get_specific_policy(client):
    """Test getting a specific policy"""
    response = client.get("/api/v1/policies/A12345")
    assert response.status_code == 200
    data = response.json()
    assert data["policy_number"] == "A12345"
    assert "name" in data
    assert "premium_amount" in data


def test_get_nonexistent_policy(client):
    """Test getting a policy that doesn't exist"""
    response = client.get("/api/v1/policies/INVALID999")
    assert response.status_code == 404
    assert "Policy not found" in response.json()["detail"]


def test_pagination(client):
    """Test pagination parameters"""
    # Get first page
    response1 = client.get("/api/v1/policies?limit=2&offset=0")
    assert response1.status_code == 200
    page1 = response1.json()
    
    # Get second page
    response2 = client.get("/api/v1/policies?limit=2&offset=2")
    assert response2.status_code == 200
    page2 = response2.json()
    
    # Should have different policies
    if page1["policies"] and page2["policies"]:
        assert page1["policies"][0]["policy_number"] != page2["policies"][0]["policy_number"]