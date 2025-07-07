# Advanced Topics

## Multi-Environment Deployment

Run multiple isolated instances of the system using deployment namespaces. This is useful for running separate environments (development, staging, production) or pull request previews.

### Configuration

Set the deployment namespace environment variable:

```bash
export DEPLOYMENT_NAMESPACE=pr-123  # or staging, prod, dev, etc.
make start-all
```

This configuration will:
- Prefix all Kafka topics (e.g., `pr-123-agents`, `pr-123-human`)
- Create separate Temporal namespaces for workflow isolation
- Use distinct Vespa application names for document storage

### Example Use Cases

1. **Pull Request Previews**
   ```bash
   export DEPLOYMENT_NAMESPACE=pr-${PR_NUMBER}
   make docker-up
   make start-all
   ```

2. **Staging Environment**
   ```bash
   export DEPLOYMENT_NAMESPACE=staging
   make start-all
   ```

3. **Production Deployment**
   ```bash
   export DEPLOYMENT_NAMESPACE=prod
   make start-all
   ```

## Agent Optimization

Optimize agent responses using DSPy's SIMBA optimizer:

### Individual Agent Optimization

```bash
make compile-billing-optimizer     # Optimize billing agent
make compile-claims-optimizer      # Optimize claims agent
make compile-policies-optimizer    # Optimize policies agent
make compile-escalation-optimizer  # Optimize escalation agent
```

### Batch Optimization

```bash
make compile-all  # Optimize all agents sequentially
```

### Triage Classifier Optimization

```bash
make compile-triage-classifier-v2  # Few-shot classifier
make compile-triage-classifier-v4  # Zero-shot COPRO optimizer
```

## Custom Model Training

Train custom triage classifiers for improved routing accuracy:

### Available Models

1. **Baseline Few-Shot Classifier (v3)**
   ```bash
   make train-triage-classifier-v3
   ```
   - Uses few-shot learning with examples
   - Good baseline performance
   - Requires training data

2. **Attention-Based Classifier (v5)**
   ```bash
   make train-triage-classifier-v5
   ```
   - Advanced neural architecture
   - Best performance on complex queries
   - Requires GPU for optimal training

### Monitoring Training Progress

View training metrics and model performance:
- MLflow UI: http://localhost:5001
- Experiments are organized by model version
- Compare runs across different hyperparameters

### Evaluating Models

```bash
make test-triage-classifier-v3  # Test baseline model
make test-triage-classifier-v5  # Test attention model
```

## Performance Tuning

### Kafka Configuration

For high-throughput scenarios, adjust Kafka settings:

```bash
# In .env
KAFKA_NUM_PARTITIONS=10
KAFKA_REPLICATION_FACTOR=3
```

### Temporal Worker Scaling

Scale Temporal workers for better throughput:

```bash
# Start multiple workers
make start-policies-document-ingestion &
make start-policies-document-ingestion &
```

### Vespa Optimization

Configure Vespa for your data volume:
- Adjust memory settings in `docker-compose.yml`
- Configure ranking profiles in `agents/policies/vespa/schemas/`
- Monitor query performance in Vespa metrics

## Monitoring and Observability

### Grafana Dashboards

Access pre-configured dashboards at http://localhost:3000:
- Agent performance metrics
- Message throughput
- Error rates and latencies

### Prometheus Metrics

Each agent exposes metrics on different ports:
- Frontend: 9090
- Triage: 9091
- Billing: 9092
- Claims: 9093
- Escalation: 9094
- Policies: 9095
- Audit: 9096

### Distributed Tracing

OpenTelemetry traces are collected and can be viewed in:
- Jaeger UI (if configured)
- MLflow trace viewer
- Custom trace analysis tools

## Production Deployment Checklist

1. **Environment Variables**
   - Set all required API keys
   - Configure production database URLs
   - Set appropriate log levels

2. **Infrastructure**
   - Use production-grade Kafka cluster
   - Deploy Vespa with multiple nodes
   - Configure Temporal with persistence

3. **Security**
   - Enable SSL/TLS for all services
   - Configure authentication
   - Set up network policies

4. **Monitoring**
   - Set up alerting rules
   - Configure log aggregation
   - Enable distributed tracing

5. **Backup and Recovery**
   - Regular Vespa index backups
   - Temporal workflow history backup
   - Database backup strategies