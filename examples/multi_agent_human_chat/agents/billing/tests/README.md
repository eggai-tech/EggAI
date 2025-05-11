# Billing Agent Tests

## Overview

The billing agent tests are structured into three primary categories to ensure comprehensive coverage while maintaining clarity:

1. **Module Tests** (`test_module.py`): Direct tests of the DSPy module without agent integration
2. **Agent Tests** (`test_agent.py`): Integration tests for the full agent with Kafka messaging
3. **Evaluation Tests** (`test_evaluation.py`): Advanced tests focusing on response evaluation

## Test Files

- **`test_module.py`**: Tests the core DSPy module directly for response quality
- **`test_agent.py`**: Tests the end-to-end agent integration with messaging
- **`test_evaluation.py`**: Uses LLM evaluators to assess response quality
- **`utils.py`**: Shared utilities and test case definitions
- `evaluation/`: Utility modules for evaluating agent responses
  - **`metrics.py`**: Functions for calculating response accuracy
  - **`report.py`**: Report generation utilities

## Running Tests

Run individual test files:

```bash
# Module tests (fastest, most reliable)
python -m pytest agents/billing/tests/test_module.py -v

# Agent integration tests
python -m pytest agents/billing/tests/test_agent.py -v

# Advanced evaluation tests
python -m pytest agents/billing/tests/test_evaluation.py -v
```

Or run all tests:

```bash
python -m pytest agents/billing/tests/
```

## Test Case Structure

Test cases are defined in `utils.py` and follow this structure:

```python
{
    "policy_number": "B67890",
    "expected_response": "Your next payment of $300.00 is due on 2025-03-15.",
    "user_messages": [
        "Hi, I'd like to know my next billing date.",
        "It's B67890."
    ],
    "agent_responses": [
        "Sure! Please provide your policy number."
    ]
}
```

Each test case automatically generates a conversation history for testing the agent.