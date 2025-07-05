from typing import Dict, List

# Sample policies for testing and demonstration
EXAMPLE_POLICIES: List[Dict] = [
    {
        "policy_number": "A12345",
        "name": "John Doe",
        "policy_category": "home",
        "premium_amount": 500,
        "due_date": "2026-03-01",
    },
    {
        "policy_number": "B67890",
        "name": "Jane Smith",
        "policy_category": "life",
        "premium_amount": 300,
        "due_date": "2026-03-15",
    },
    {
        "policy_number": "C24680",
        "name": "Alice Johnson",
        "policy_category": "auto",
        "premium_amount": 400,
        "due_date": "2026-03-01",
    },
]

# This would typically come from environment configuration
USE_EXAMPLE_DATA = True  # Set to False in production