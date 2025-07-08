# EggAI Libraries

A well-organized collection of utilities and infrastructure for building AI agents with EggAI.

## Structure

The libraries are organized into logical modules based on functionality:

### 📦 Core (`core/`)
Fundamental building blocks used across all agents.
- **config.py**: `BaseAgentConfig` - Base configuration class for agents
- **models.py**: `ModelConfig`, `ModelResult` - Data models for ML operations
- **patches.py**: System patches for DSPy usage tracking

### 📡 Communication (`communication/`)
Message passing and transport infrastructure.
- **channels.py**: Channel configuration with deployment namespace support
- **messaging.py**: Type-safe message subscription decorator
- **transport.py**: Kafka transport with SSL support
- **protocol/**: Message protocol definitions (types, enums, documentation)

### 🤖 ML (`ml/`)
Machine learning utilities and integrations.
- **device.py**: PyTorch device selection utilities
- **mlflow.py**: MLflow model artifact management
- **dspy/**: DSPy-specific utilities
  - **language_model.py**: Language model wrapper with token tracking
  - **optimizer.py**: SIMBA optimizer for DSPy modules

### 📊 Observability (`observability/`)
Monitoring, logging, and debugging tools.
- **logger/**: Structured logging with colored output
- **tracing/**: OpenTelemetry integration
  - Distributed tracing
  - Metrics collection
  - Token usage and pricing calculations

### 🔌 Integrations (`integrations/`)
External service connectors.
- **vespa/**: Vespa search engine client for document retrieval

### 🧪 Testing (`testing/`)
Test utilities and unit tests.
- **utils/**: Reusable test helpers
  - Agent testing utilities
  - DSPy test helpers
  - MLflow tracking for tests
- **tests/**: Unit tests for library components

## Usage

Import from specific modules:
```python
from libraries.communication import channels, subscribe
from libraries.core import BaseAgentConfig
from libraries.observability import get_console_logger, TracedMessage
from libraries.ml.dspy import get_language_model
from libraries.integrations.vespa import VespaClient
```

## Key Features

- **Type Safety**: Strongly typed message protocols with TypedDict
- **Observability**: Built-in tracing, logging, and metrics
- **Scalability**: Deployment namespace support for multi-environment setups
- **Testing**: Comprehensive test utilities for agent development
- **Modularity**: Clean separation of concerns for easy maintenance

## Design Principles

1. **Clear Organization**: Each module has a single, well-defined purpose
2. **Minimal Dependencies**: Modules are loosely coupled
3. **Type Safety**: Extensive use of type hints and validation
4. **Testability**: All components are designed to be easily testable
5. **Extensibility**: Easy to add new functionality within established patterns