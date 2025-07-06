"""Tests for Billing API endpoints"""
import pytest
from fastapi.testclient import TestClient

from agents.billing.api_main import app


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "billing-agent-api",
        "version": "1.0.0"
    }


def test_list_billing_records(client):
    """Test list billing records endpoint"""
    response = client.get("/api/v1/billing?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "total" in data
    assert isinstance(data["records"], list)


def test_list_billing_with_filters(client):
    """Test list billing with status filter"""
    response = client.get("/api/v1/billing?status=Pending&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    # Check all returned records have the correct status
    for record in data["records"]:
        assert record["status"] == "Pending"


def test_get_billing_by_policy(client):
    """Test get specific billing record"""
    response = client.get("/api/v1/billing/A12345")
    assert response.status_code == 200
    data = response.json()
    assert data["policy_number"] == "A12345"
    assert data["customer_name"] == "John Doe"


def test_get_nonexistent_billing(client):
    """Test get billing that doesn't exist"""
    response = client.get("/api/v1/billing/Z99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_billing_statistics(client):
    """Test billing statistics endpoint"""
    response = client.get("/api/v1/billing/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_records" in data
    assert "total_amount_due" in data
    assert "total_amount_paid" in data
    assert "overdue_count" in data
    assert "by_status" in data
    assert "by_cycle" in data
    assert "average_amount" in data


def test_billing_cycle_filter(client):
    """Test filtering by billing cycle"""
    response = client.get("/api/v1/billing?billing_cycle=Monthly")
    assert response.status_code == 200
    data = response.json()
    for record in data["records"]:
        assert record["billing_cycle"] == "Monthly"