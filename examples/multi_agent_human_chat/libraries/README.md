# Libraries

Shared utilities and infrastructure for EggAI agents.

## Structure

### Core (`core/`)
- `BaseAgentConfig` - Base configuration class
- `ModelConfig`, `ModelResult` - ML data models
- System patches for DSPy tracking

### Communication (`communication/`)
- `channels.py` - Channel configuration with namespacing
- `messaging.py` - Type-safe message subscription
- `transport.py` - Kafka transport with SSL
- `protocol/` - Message types and enums

### ML (`ml/`)
- `device.py` - PyTorch device utilities
- `mlflow.py` - Model artifact management
- `dspy/` - Language model wrapper and optimizer

### Observability (`observability/`)
- `logger/` - Structured logging
- `tracing/` - OpenTelemetry, metrics, pricing

### Integrations (`integrations/`)
- `vespa/` - Document search client

### Testing (`testing/`)
- `utils/` - Test helpers
- `tests/` - Unit tests

## Usage

```python
from libraries.communication import channels, subscribe
from libraries.core import BaseAgentConfig
from libraries.observability import get_console_logger
from libraries.ml.dspy import dspy_set_language_model
```