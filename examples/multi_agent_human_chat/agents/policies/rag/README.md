# Policy RAG with Temporal Workflows

A sophisticated Retrieval-Augmented Generation (RAG) system for insurance policy documents, leveraging Temporal workflows for robust documentation query orchestration and RAGatouille for high-performance semantic search.

## Why RAG + Temporal?

### The Challenge of Long-Running RAG Workflows

Traditional RAG systems face several challenges when dealing with complex, multi-step retrieval and generation workflows:

- **Network Failures**: Long-running processes can fail due to network interruptions
- **Resource Constraints**: Memory limitations during large document processing
- **Error Recovery**: Difficult to resume workflows from failure points
- **Observability**: Limited visibility into multi-step retrieval pipelines
- **Scalability**: Hard to distribute processing across multiple workers

### Temporal's Solution for RAG

Temporal provides a **durable execution platform** that makes RAG workflows:

- **🔄 Fault-Tolerant**: Automatic retries and state recovery
- **👀 Observable**: Complete visibility into workflow execution
- **⚡ Scalable**: Distribute work across multiple workers
- **🎯 Reliable**: Guaranteed execution even with failures
- **📊 Auditable**: Full history of all workflow steps

## RAGatouille: State-of-the-Art Retrieval

This system uses [RAGatouille](https://github.com/bclavie/RAGatouille), a powerful retrieval library built on **ColBERT** (Contextualized Late Interaction over BERT):

### Why RAGatouille?
- **🚀 Performance**: ColBERT's late interaction mechanism provides superior relevance
- **💾 Efficiency**: Compressed embeddings reduce storage requirements
- **🎯 Accuracy**: Better semantic understanding compared to traditional embeddings
- **⚖️ Scalable**: Handles large document collections efficiently

### ColBERT Architecture
ColBERT uses a unique "late interaction" approach:
1. **Query Encoding**: Encodes queries into contextualized embeddings
2. **Document Encoding**: Pre-computes document embeddings offline
3. **Late Interaction**: Performs fine-grained matching at query time
4. **Result Ranking**: Provides highly relevant results with fast retrieval

## System Architecture

### Two-Tier Retrieval Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Policy RAG System                        │
├─────────────────────────────────────────────────────────────┤
│  Simple Queries          │  Complex Documentation Queries   │
│                          │                                   │
│  retrieve_policies()     │  query_policy_documentation()     │
│  ↓                       │  ↓                                │
│  RAGatouille             │  Temporal Workflow                │
│  (Direct)                │  ↓                                │
│                          │  RAGatouille + Orchestration      │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. **RAGatouille Retrieval Engine** (`retrieving.py`)
- **ColBERT-powered search** for semantic document retrieval
- **Index management** with automatic loading and caching
- **Category filtering** for targeted policy searches
- **High-performance** direct queries without workflow overhead

#### 2. **Temporal Documentation Workflows** (`workflows/`)
For complex, long-running documentation queries that benefit from:
- **Fault tolerance** during multi-step retrieval processes
- **State persistence** across workflow steps  
- **Retry mechanisms** for transient failures
- **Distributed execution** across worker nodes

**Components:**
- `documentation_workflow.py` - Orchestrates complex documentation retrieval
- `retrieval_activity.py` - Temporal activity wrapping RAGatouille calls
- `worker.py` - Temporal worker handling documentation workflows

#### 3. **Smart Query Router** (`policies_data.py`)
The `query_policy_documentation()` function intelligently routes queries:
```python
# First: Attempt Temporal workflow (for reliability)
# Fallback: Direct RAGatouille retrieval (for availability)
```

### When to Use Each Approach

| Use Case | Method | Why |
|----------|--------|-----|
| **Quick policy lookups** | `retrieve_policies()` | Fast, direct access |
| **Complex documentation queries** | `query_policy_documentation()` | Fault-tolerant, auditable |
| **High-volume simple searches** | Direct RAGatouille | Low latency, no overhead |
| **Multi-step analysis workflows** | Temporal workflow | Durable, observable, scalable |

## Benefits of This Hybrid Approach

### ⚡ **Performance**
- Simple queries: Direct RAGatouille access (sub-second response)
- Complex queries: Temporal orchestration (reliable execution)

### 🛡️ **Reliability** 
- Documentation workflows survive failures and resume automatically
- Direct retrieval provides immediate fallback for availability

### 📊 **Observability**
- Temporal UI shows complete workflow execution history
- Detailed logging for both direct and workflow-based retrieval

### 🎯 **Scalability**
- Direct retrieval scales with RAGatouille's performance
- Temporal workflows distribute across multiple workers

## Quick Start

### 1. Launch the Complete System

```bash
make start
```

This starts:
- **Temporal Server** (orchestration platform)
- **Policy Documentation Worker** (handles complex queries)
- **All Insurance Agents** (including policies agent)
- **Supporting Services** (PostgreSQL, monitoring, etc.)

### 2. Verify RAGatouille Index

The system automatically builds the ColBERT index on first use:

```bash
python agents/policies/rag/test_simple_documentation.py
```

### 3. Usage Examples

#### Simple Policy Retrieval (Direct RAGatouille)
```python
from agents.policies.rag.retrieving import retrieve_policies

# Fast, direct semantic search
results = retrieve_policies("fire damage coverage", category="home")
# Returns: List of relevant policy documents with scores
```

#### Complex Documentation Queries (Temporal + RAGatouille)
```python
from agents.policies.dspy_modules.policies_data import query_policy_documentation

# Fault-tolerant workflow execution
docs = query_policy_documentation("coverage exclusions and limitations", "auto")
# Returns: JSON-formatted documentation with citations
```

## Advanced Usage

### Manual Worker Management

Start only the documentation worker:
```bash
make start-policy-documentation-worker
```

With custom Temporal configuration:
```bash
python agents/policies/rag/start_worker.py \
  --server-url temporal.company.com:7233 \
  --namespace production \
  --task-queue policy-documentation
```

### Direct Temporal Client Usage

For building custom workflows on top of the documentation system:

```python
import asyncio
from agents.policies.rag.documentation_temporal_client import DocumentationTemporalClient

async def complex_analysis():
    client = DocumentationTemporalClient()
    
    # Execute with full workflow observability
    result = await client.query_documentation_async(
        query="multi-policy coverage interactions",
        policy_category="auto",
        request_id="analysis-001"
    )
    
    if result.success:
        print(f"Found {len(result.results)} relevant documents")
        return result.results
    else:
        print(f"Workflow failed: {result.error_message}")
        return []
    
    await client.close()

# Run the async function
results = asyncio.run(complex_analysis())
```

## API Reference

### Core Functions

#### `retrieve_policies(query, category=None)`
Direct RAGatouille-powered retrieval for simple, fast queries.

```python
from agents.policies.rag.retrieving import retrieve_policies

results = retrieve_policies(
    query="fire damage coverage",    # Search query
    category="home"                  # Optional: "auto", "home", "life", "health"
)
# Returns: List[Dict] with document content and metadata
```

#### `query_policy_documentation(query, policy_category)`
Temporal workflow-orchestrated retrieval for complex documentation queries.

```python
from agents.policies.dspy_modules.policies_data import query_policy_documentation

docs = query_policy_documentation(
    query="coverage exclusions and limitations",
    policy_category="auto"           # Required: policy category
)
# Returns: JSON string with formatted documentation results
```

### Temporal Client (Advanced)

#### `DocumentationTemporalClient`
Direct access to Temporal workflows for custom integrations.

```python
from agents.policies.rag.documentation_temporal_client import DocumentationTemporalClient

client = DocumentationTemporalClient(
    temporal_server_url="localhost:7233",    # Temporal server
    temporal_namespace="default",            # Temporal namespace  
    temporal_task_queue="policy-rag"        # Task queue name
)

# Execute workflow
result = await client.query_documentation_async(query, category, request_id)
```

## Configuration

### Temporal Settings

Configure in `workflows/worker.py` or via constructor:

```python
class PolicyDocumentationWorkerSettings:
    temporal_server_url: str = "localhost:7233"
    temporal_namespace: str = "default" 
    temporal_task_queue: str = "policy-rag"
```

### RAGatouille Index

The ColBERT index is built automatically from policy documents in:
- `agents/policies/rag/policies/` (markdown files)

To rebuild the index:
```python
from agents.policies.rag.indexing import ensure_index_built
ensure_index_built(force_rebuild=True)
```

## Monitoring & Observability

### Temporal Web UI
Monitor workflow execution at: **http://localhost:8081**

- View running workflows
- Inspect workflow history
- Debug failed executions
- Monitor worker health

### Logging
Structured logging with correlation IDs:

```bash
# Worker logs
make start-policy-documentation-worker

# Test system health  
python agents/policies/rag/test_simple_documentation.py
```

### Metrics
Key metrics to monitor:
- **Direct retrieval latency**: Sub-second for most queries
- **Workflow success rate**: Should be >99% with retries
- **Fallback frequency**: Indicates Temporal health
- **Index query performance**: ColBERT search times

## Production Deployment

### Scaling Considerations

1. **RAGatouille Performance**
   - Index size scales with document collection
   - Memory usage: ~2-4GB for large policy sets
   - Query latency: 50-200ms typical

2. **Temporal Workers**
   - Scale workers horizontally for documentation query load
   - Each worker handles ~10-50 concurrent workflows
   - CPU-bound: prefer more cores over more memory

3. **High Availability**
   - Run multiple Temporal workers across nodes
   - Direct retrieval provides automatic fallback
   - Index can be shared across worker instances

### Security

- **Network**: Secure Temporal server communication
- **Data**: Policy documents contain sensitive information
- **Access**: Control worker deployment and scaling

### Development

To extend the system:

1. **Add new activities**: Create in `workflows/activities/`
2. **Extend workflows**: Modify `documentation_workflow.py`
3. **Custom clients**: Build on `DocumentationTemporalClient`

---

**Learn More:**
- [Temporal Documentation](https://docs.temporal.io/)
- [RAGatouille GitHub](https://github.com/bclavie/RAGatouille)
- [ColBERT Paper](https://arxiv.org/abs/2004.12832)