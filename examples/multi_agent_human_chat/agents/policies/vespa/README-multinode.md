# Vespa Multi-Node Setup

Multi-node Vespa cluster matching production environment.

## Quick Start

```bash
# Start cluster
make docker-up

# Wait 2-3 minutes for initialization, then deploy
make deploy-vespa-package

# Stop cluster
make docker-down
```

## Architecture

- 1 Config Server (vespa-configserver)
- 3 Service Nodes (vespa-node-0, vespa-node-1, vespa-node-2)
- Redundancy: 2

## Endpoints

- Query API: http://localhost:8080
- Config API: http://localhost:19071
- Additional nodes: http://localhost:8081, http://localhost:8082

## Files

- `hosts-docker-local.json`: Docker host mappings
- `example-hosts.json`: Kubernetes example

## Troubleshooting

```bash
# Check status
curl http://localhost:19071/state/v1/health
curl http://localhost:8080/state/v1/health

# Force redeploy
make deploy-vespa-package ARGS="--force"

# Reset cluster
make docker-down
make docker-up
```