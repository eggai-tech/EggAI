# Admin Dashboard

## Overview

The unified admin dashboard provides a comprehensive view of all system data and operations. It combines real-time monitoring of policies, claims, billing, and knowledge base management into a single interface.

## Features

### Overview Tab
- **System Statistics**: Real-time counts of policies, claims, billing records, and indexed documents
- **API Status Monitor**: Shows online/offline status for all agent APIs
- **Recent Activity**: Displays latest claims and billing overview

### Policies Tab
- View all active insurance policies
- Search by policy number or customer name
- Click on any policy to see detailed information
- Real-time data from the policies agent

### Claims Tab
- Browse all insurance claims with status indicators
- Filter and search claims
- Click on claims to view outstanding items and details
- Requires Claims API to be running on port 8003

### Billing Tab
- View all billing records and payment status
- Monitor overdue payments
- Track payment cycles
- Requires Billing API to be running on port 8004

### Knowledge Base Tab
- Manage indexed policy documents
- View document chunks and embeddings
- Search through documentation
- Monitor indexing status

### System Tab
- Quick links to all platform services:
  - Redpanda (Kafka) UI
  - Temporal Workflow UI
  - Grafana Dashboards
  - MLflow Experiments
  - Vespa Search
  - Prometheus Metrics

## Starting Required Services

### Start Everything
```bash
# Start infrastructure
docker-compose up -d

# Start all agents (includes all APIs)
make start-all
```

This will start:
- Frontend agent with admin UI (port 8000)
- Policies agent with API (port 8002)
- Claims agent with API (port 8003)
- Billing agent with API (port 8004)
- Triage and escalation agents

### Individual Agent Startup
You can also start agents individually:
```bash
make start-frontend   # Admin UI
make start-policies   # Policies API
make start-claims     # Claims API
make start-billing    # Billing API
```

## Accessing the Dashboard

1. Start the frontend agent: `make start-frontend`
2. Open your browser to: http://localhost:8000/admin.html
3. The dashboard will automatically check which APIs are available

## API Availability

The admin dashboard gracefully handles API availability:
- If an API is offline, you'll see a helpful message with instructions to start it
- The Overview tab shows real-time API status
- Data is fetched only from available APIs

## Troubleshooting

### "Failed to load claims/billing data"
This means the respective agent is not running. Start it using:
```bash
make start-claims   # For claims API
make start-billing  # For billing API

# Or start all agents at once:
make start-all
```

### Empty or missing data
1. Ensure the policies agent is running: `make start-policies`
2. Check that infrastructure is up: `docker-compose ps`
3. Verify data has been ingested into the system

### Cannot access platform services
Platform service links (Grafana, Temporal, etc.) require Docker infrastructure to be running:
```bash
docker-compose up -d
```