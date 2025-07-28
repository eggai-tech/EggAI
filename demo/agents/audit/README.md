# Audit Agent

The Audit Agent monitors all system activity for compliance, security, and operational insights.

- **Purpose**: Monitors and logs all system activity
- **Key Features**:
  - Captures all messages on `human` and `agents` channels
  - Categorizes messages by domain
  - Creates standardized audit records
  - Publishes to `audit_logs` channel
- **Purpose**:
  - Compliance reporting
  - Message filtering and analysis
  - Real-time monitoring of system health

## Quick Start

```bash
# From the project root
make start-audit

# Or run directly
python -m agents.audit.main
```

### Configuration

Key environment variables:

```bash
AUDIT_PROMETHEUS_METRICS_PORT=9096
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_FILE=./audit_logs/audit.log
```

## Monitoring Capabilities

The Audit Agent monitors:

1. **Message Flow**
   - All messages between agents
   - User requests and agent responses
   - Message types and routing decisions

2. **Performance Metrics**
   - Response times per agent
   - Message processing rates
   - Error rates and types

3. **Compliance Data**
   - User data access patterns
   - Policy number usage
   - Sensitive information handling

### Querying Audit Logs

#### Example Queries

```python
# Find all billing-related messages
grep '"source": "Billing"' audit_logs/audit.log

# Track specific user session
grep '"connection_id": "user-123"' audit_logs/audit.log

# Find errors
grep '"level": "ERROR"' audit_logs/audit.log
```

### Log Format

```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "message_id": "uuid",
  "source": "Billing",
  "type": "agent_message",
  "connection_id": "user-connection-id",
  "content_preview": "First 100 chars...",
  "trace_id": "opentelemetry-trace-id"
}
```

## Development

### Testing

```bash
# Run audit agent tests
make test-audit-agent

# Run specific test files
pytest agents/audit/tests/test_agent.py -v
```

### Custom Log Processing

The audit agent can be extended with custom processors:

```python
# Add custom message analyzer
def analyze_pii(message):
    # Check for personally identifiable information
    return has_pii, pii_types

# Register with audit agent
audit_agent.add_processor(analyze_pii)
```

### Integration with External Systems

Export audit logs to external systems:

- Elasticsearch for search
- Splunk for analysis
- S3 for long-term storage

## Architecture

- **Input Channels**: Monitors all system channels
  - `agents` - Inter-agent communication
  - `human` - User interactions
  - `human_stream` - Streaming responses
- **Storage**: Local file system with rotation
- **Processing**: Real-time analysis pipeline
- **Export**: Configurable log forwarding

## Compliance Features

- **Data Privacy**: Masks sensitive information
- **Retention**: Configurable log retention policies
- **Access Control**: Audit log access restrictions
- **Reporting**: Compliance report generation

## Monitoring

- Prometheus metrics: http://localhost:9096/metrics
- Log volume and processing rates
- Anomaly detection alerts
- System health indicators
