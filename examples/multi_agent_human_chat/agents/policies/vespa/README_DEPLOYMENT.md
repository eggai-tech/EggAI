# Vespa Deployment Guide

## Overview

This guide covers deploying the Vespa application package for the policies search system.

## Local Development (Single Node)

For local development, use single-node deployment:

```bash
# Deploy single-node configuration
make deploy-vespa-package ARGS="--deployment-mode local --node-count 1"
```

## Production Deployment (Multi-Node)

For production Kubernetes deployment:

```bash
# Set environment variables
export VESPA_CONFIG_SERVER=http://vespa-configserver-0.vespa-internal.my-namespace.svc.cluster.local:19071
export VESPA_QUERY_URL=http://vespa-query-0.vespa-internal.my-namespace.svc.cluster.local:8080
export VESPA_DEPLOYMENT_MODE=production
export VESPA_NODE_COUNT=3

# Deploy
make deploy-vespa-package
```

## Configuration Details

### Environment Variables

- `VESPA_CONFIG_SERVER`: URL of the Vespa config server
- `VESPA_QUERY_URL`: URL for Vespa query endpoint
- `VESPA_DEPLOYMENT_MODE`: Either 'local' or 'production'
- `VESPA_NODE_COUNT`: Number of nodes (for production mode)
- `KUBERNETES_NAMESPACE`: Automatically detected in Kubernetes
- `VESPA_SERVICE_NAME`: Service name prefix (default: vespa-node)

### Generated Files

The deployment process generates:

1. **services.xml**: Contains cluster configuration
   - Admin section with cluster controllers (multi-node only)
   - Container cluster configuration
   - Content cluster with redundancy settings

2. **hosts.xml**: Maps host aliases to actual hostnames (multi-node only)
   - Automatically generated based on environment
   - Uses Kubernetes service names in K8s environment

3. **Schema files**: Document schema definitions
   - policy_document schema with all fields
   - Rank profiles for different search strategies

## Multi-Node Architecture

In production (Kubernetes):
- **Config Server**: Manages cluster configuration
- **Container Nodes**: Handle search queries and document processing
- **Content Nodes**: Store and index documents
- **Cluster Controllers**: Coordinate multi-node operations

## Known Limitations

### Docker Compose (Local)
- Multi-node Vespa has coordination issues in Docker Compose
- ZooKeeper embedded in Vespa doesn't start properly in local Docker
- Recommended to use single-node for local development

### Production Requirements
- Kubernetes environment required for proper multi-node operation
- Service discovery and network configuration handled by Kubernetes
- Minimum 3 nodes recommended for redundancy

## Deployment Verification

After deployment:

```bash
# Check application status
curl http://localhost:8080/ApplicationStatus

# Test search
curl "http://localhost:8080/search/?yql=select%20*%20from%20policy_document%20where%20true%20limit%201"

# Check health
curl http://localhost:8080/state/v1/health
```

## Troubleshooting

### Connection Reset Errors
- Normal during initial deployment
- Wait 30-60 seconds for nodes to initialize

### Backend Communication Errors (Multi-Node)
- In Docker: Expected due to ZooKeeper issues
- In Kubernetes: Check service connectivity and DNS

### Schema Not Found
- Ensure deployment completed successfully
- Check config server logs for errors
- Verify application package was activated

## DevOps Configuration Guide

For DevOps engineers setting up production deployment:

### Kubernetes Resources Needed

1. **ConfigMap** for Vespa configuration
2. **StatefulSet** for Vespa nodes (ensures stable network identities)
3. **Services**:
   - Config server service (port 19071)
   - Query service (port 8080)
   - Internal service for node communication
4. **PersistentVolumeClaims** for data persistence

### Example Kubernetes Service Definition

```yaml
apiVersion: v1
kind: Service
metadata:
  name: vespa-internal
spec:
  clusterIP: None
  selector:
    app: vespa
  ports:
    - name: container
      port: 8080
    - name: config
      port: 19071
```

### Resource Requirements

- **CPU**: Minimum 2 cores per node
- **Memory**: Minimum 4GB per node
- **Storage**: 50GB+ per content node
- **Network**: Low latency between nodes critical

### Monitoring

Key metrics to monitor:
- Query latency
- Document feed rate
- Disk usage
- Memory usage
- Cluster controller status

### Scaling

- Can scale container nodes independently
- Content nodes require rebalancing when scaled
- Minimum 3 nodes for fault tolerance