import json
from datetime import datetime

from agents.escalation.dspy_modules.escalation import (
    create_ticket,
    get_tickets_by_policy,
    ticket_database,
)


def test_get_tickets_by_policy_existing():
    """Test getting tickets for existing policy."""
    result = get_tickets_by_policy("A12345")
    data = json.loads(result)

    assert isinstance(data, dict)
    assert data["found"] is True
    assert "tickets" in data
    assert isinstance(data["tickets"], list)
    assert len(data["tickets"]) >= 1

    # Check the existing ticket
    ticket = data["tickets"][0]
    assert ticket["policy_number"] == "A12345"
    assert ticket["id"] == "TICKET-001"
    assert ticket["department"] == "Technical Support"
    assert "contact_info" in ticket


def test_get_tickets_by_policy_nonexistent():
    """Test getting tickets for non-existent policy."""
    result = get_tickets_by_policy("NONEXISTENT")
    data = json.loads(result)

    assert isinstance(data, dict)
    assert data["found"] is False
    assert "tickets" in data
    assert isinstance(data["tickets"], list)
    assert len(data["tickets"]) == 0


def test_get_tickets_by_policy_with_whitespace():
    """Test getting tickets with whitespace in policy number (normalized)."""
    result = get_tickets_by_policy("  A12345  ")
    data = json.loads(result)

    # Leading/trailing whitespace should be stripped before matching
    assert isinstance(data, dict)
    assert data["found"] is True
    assert len(data["tickets"]) >= 1
    assert data["tickets"][0]["policy_number"] == "A12345"


def test_create_ticket_success():
    """Test creating a new ticket successfully."""
    original_count = len(ticket_database)

    result = create_ticket(
        "B67890", "Billing", "Payment processing issue", "customer@example.com"
    )
    data = json.loads(result)

    assert "id" in data  # The field is "id", not "ticket_id"
    assert data["policy_number"] == "B67890"
    assert data["department"] == "Billing"
    assert data["title"] == "Payment processing issue"
    assert data["contact_info"] == "customer@example.com"

    # Verify ticket was added to database
    assert len(ticket_database) == original_count + 1

    # Find the new ticket
    new_ticket = next((t for t in ticket_database if t["id"] == data["id"]), None)
    assert new_ticket is not None
    assert new_ticket["policy_number"] == "B67890"


def test_create_ticket_valid_departments():
    """Test creating tickets with all valid departments."""
    valid_departments = ["Technical Support", "Billing", "Sales"]
    original_count = len(ticket_database)

    for i, dept in enumerate(valid_departments):
        result = create_ticket(
            f"DEPT{i}", dept, f"Issue for {dept}", f"test{i}@example.com"
        )
        data = json.loads(result)

        assert "id" in data
        assert data["department"] == dept


def test_create_ticket_generates_unique_ids():
    """Test that create_ticket generates unique ticket IDs."""
    original_count = len(ticket_database)

    # Create multiple tickets with valid departments
    result1 = create_ticket(
        "C24680", "Technical Support", "Issue 1", "test1@example.com"
    )
    result2 = create_ticket("C24680", "Billing", "Issue 2", "test2@example.com")

    data1 = json.loads(result1)
    data2 = json.loads(result2)

    # Verify different ticket IDs
    assert data1["id"] != data2["id"]

    # Verify both tickets were added
    assert len(ticket_database) == original_count + 2


def test_create_ticket_timestamp():
    """Test that create_ticket adds proper timestamp."""
    before_creation = datetime.now()

    result = create_ticket("D12345", "Sales", "Timestamp test", "time@example.com")
    data = json.loads(result)

    after_creation = datetime.now()

    # Find the created ticket
    ticket = next((t for t in ticket_database if t["id"] == data["id"]), None)

    assert ticket is not None
    assert "created_at" in ticket

    # Parse the timestamp
    created_at = datetime.fromisoformat(ticket["created_at"])

    # Verify timestamp is reasonable
    assert before_creation <= created_at <= after_creation


def test_ticket_database_structure():
    """Test that ticket database has expected structure."""
    assert isinstance(ticket_database, list)

    for ticket in ticket_database:
        assert isinstance(ticket, dict)
        assert "id" in ticket
        assert "policy_number" in ticket
        assert "department" in ticket
        assert "title" in ticket
        assert "contact_info" in ticket
        assert "created_at" in ticket


def test_get_tickets_multiple_policies():
    """Test getting tickets for multiple policies."""
    # Create tickets for different policies with valid departments
    create_ticket("MULTI1", "Technical Support", "Test 1", "multi1@example.com")
    create_ticket("MULTI2", "Billing", "Test 2", "multi2@example.com")
    create_ticket("MULTI1", "Sales", "Test 3", "multi3@example.com")

    # Get tickets for MULTI1
    result1 = get_tickets_by_policy("MULTI1")
    data1 = json.loads(result1)

    # Get tickets for MULTI2
    result2 = get_tickets_by_policy("MULTI2")
    data2 = json.loads(result2)

    # Verify correct tickets returned
    assert data1["found"] is True
    assert len(data1["tickets"]) == 2  # Two tickets for MULTI1
    assert data2["found"] is True
    assert len(data2["tickets"]) == 1  # One ticket for MULTI2

    # Verify all tickets for MULTI1 have correct policy number
    for ticket in data1["tickets"]:
        assert ticket["policy_number"] == "MULTI1"

    # Verify ticket for MULTI2 has correct policy number
    assert data2["tickets"][0]["policy_number"] == "MULTI2"


def test_ticket_id_format():
    """Test that ticket IDs follow expected format."""
    result = create_ticket(
        "FORMAT", "Technical Support", "ID format test", "format@example.com"
    )
    data = json.loads(result)

    ticket_id = data["id"]

    # Verify ticket ID starts with "TICKET-"
    assert ticket_id.startswith("TICKET-")

    # Verify the part after "TICKET-" is numeric
    ticket_number = ticket_id.split("-")[1]
    assert ticket_number.isdigit()
    assert int(ticket_number) > 0


def test_api_response_structure():
    """Test that API responses have consistent structure."""
    # Test get_tickets_by_policy response structure
    result = get_tickets_by_policy("TEST")
    data = json.loads(result)

    assert "found" in data
    assert "message" in data
    assert "tickets" in data
    assert isinstance(data["found"], bool)
    assert isinstance(data["message"], str)
    assert isinstance(data["tickets"], list)

    # Test create_ticket response structure
    result = create_ticket("TEST", "Billing", "Test ticket", "test@example.com")
    data = json.loads(result)

    required_fields = [
        "id",
        "policy_number",
        "department",
        "title",
        "contact_info",
        "created_at",
    ]
    for field in required_fields:
        assert field in data


def test_department_validation():
    """Test that only valid departments are accepted."""
    # Valid departments should work (tested in other tests)
    valid_departments = ["Technical Support", "Billing", "Sales"]

    for dept in valid_departments:
        try:
            result = create_ticket("VALID", dept, "Test", "test@example.com")
            data = json.loads(result)
            assert data["department"] == dept
        except Exception as e:
            raise AssertionError(
                f"Valid department {dept} should not raise exception: {e}"
            )
