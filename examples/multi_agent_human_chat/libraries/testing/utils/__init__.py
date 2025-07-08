"""
Test utilities for EggAI agents.

This package provides common testing utilities, fixtures, and helpers for testing
EggAI agents and their components.

## Modules:

- fixtures: Common test data and message creation utilities
- helpers: MLflow tracking and general test helpers
- dspy_helpers: DSPy-specific test utilities
- agent_helpers: Agent-specific test utilities and assertions

## Usage:

```python
from libraries.testing.utils import create_message_list, wait_for_agent_response
from libraries.test_utils.dspy_helpers import test_signature_structure
from libraries.test_utils.agent_helpers import create_mock_agent_response
```
"""

from .agent_helpers import (
    assert_valid_agent_response,
    create_mock_agent_response,
    create_mock_audit_log,
    create_mock_request_message,
    wait_for_message_with_timeout,
)
from .dspy_helpers import (
    test_model_config_validation,
    test_optimized_dspy_basic,
    test_optimized_dspy_empty_conversation,
    test_signature_fields,
    test_signature_structure,
    test_truncate_long_history_edge_cases,
    test_truncate_long_history_return_structure,
    test_truncate_long_history_with_config,
)
from .fixtures import (
    create_conversation_string,
    create_message_list,
    wait_for_agent_response,
)
from .helpers import MLflowTracker, setup_mlflow_tracking

__all__ = [
    # From fixtures
    "create_message_list",
    "create_conversation_string",
    "wait_for_agent_response",
    # From helpers
    "MLflowTracker",
    "setup_mlflow_tracking",
    # From dspy_helpers
    "test_truncate_long_history_edge_cases",
    "test_signature_structure",
    "test_signature_fields",
    "test_optimized_dspy_basic",
    "test_optimized_dspy_empty_conversation",
    "test_model_config_validation",
    "test_truncate_long_history_with_config",
    "test_truncate_long_history_return_structure",
    # From agent_helpers
    "create_mock_agent_response",
    "create_mock_request_message",
    "wait_for_message_with_timeout",
    "create_mock_audit_log",
    "assert_valid_agent_response",
]