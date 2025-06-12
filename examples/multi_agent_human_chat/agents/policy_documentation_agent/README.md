# Policy Documentation Agent

A modular RAG (Retrieval-Augmented Generation) system for querying policy documentation. This agent decouples the traditional RAG pipeline into three separate, communicating components: Retrieval, Augmentation, and Generation.

## Architecture

The system consists of four main components:

### 1. Retrieval Agent (`components/retrieval_agent.py`)
- **Purpose**: Searches and retrieves relevant policy documents
- **Input**: Query string and optional category filter
- **Output**: List of relevant documents with metadata and relevance scores
- **Features**:
  - Uses ColBERT for semantic search
  - Maintains document index with policy categories
  - Supports category-based filtering

### 2. Augmenting Agent (`components/augmenting_agent.py`)
- **Purpose**: Combines retrieved documents with conversation context
- **Input**: Query, retrieved documents, and conversation history
- **Output**: Augmented context ready for generation
- **Features**:
  - Intelligent document ranking and selection
  - Context length management
  - Conversation history integration

### 3. Generation Agent (`components/generation_agent.py`)
- **Purpose**: Generates final responses based on augmented context
- **Input**: Augmented context with policy information
- **Output**: Generated response with proper citations
- **Features**:
  - Streaming and non-streaming response modes
  - Policy-aware response generation
  - Automatic citation of sources

### 4. Main Orchestrator Agent (`agent.py`)
- **Purpose**: Coordinates communication between components
- **Features**:
  - Inter-agent communication management
  - Request routing and response aggregation
  - Error handling and recovery
  - Streaming support for real-time responses

## Message Flow

```
User Query → Orchestrator → Retrieval Agent → Documents
                ↓
Orchestrator ← Augmenting Agent ← Documents + Context
                ↓
Generation Agent ← Augmented Context
                ↓
User Response ← Orchestrator ← Generated Response
```

## Configuration

Configuration is managed through `config.py` with environment variable support:

```python
# Model settings
POLICY_DOC_AGENT_MODEL_NAME=gpt-4
POLICY_DOC_AGENT_TEMPERATURE=0.1

# RAG settings  
POLICY_DOC_AGENT_MAX_DOCUMENTS_PER_QUERY=5
POLICY_DOC_AGENT_MAX_CONTEXT_LENGTH=4000

# Timeout settings
POLICY_DOC_AGENT_DEFAULT_TIMEOUT_SECONDS=30.0
```

## Usage

### Running the Complete System

```bash
python -m agents.policy_documentation_agent.main
```

### Testing Individual Components

```bash
# Test retrieval
python -m agents.policy_documentation_agent.components.retrieval_agent

# Test augmentation  
python -m agents.policy_documentation_agent.components.augmenting_agent

# Test generation
python -m agents.policy_documentation_agent.components.generation_agent
```

### Integration with Other Agents

The agent listens for `documentation_request` messages on the agents channel:

```python
await agents_channel.publish(
    TracedMessage(
        type="documentation_request",
        source="SomeOtherAgent", 
        data={
            "chat_messages": chat_messages,
            "connection_id": connection_id,
            "streaming": True
        }
    )
)
```

## Message Types

### Internal Communication

- `retrieval_request` / `retrieval_response`
- `augmentation_request` / `augmentation_response` 
- `generation_request` / `generation_response`
- `generation_stream_start` / `generation_stream_chunk` / `generation_stream_end`

### External Communication

- Input: `documentation_request` (from agents channel)
- Output: `agent_message` or streaming messages (to human channels)

## Policy Documents

Policy documents are stored in the `policies/` directory:
- `auto.md` - Auto insurance policies
- `health.md` - Health insurance policies  
- `home.md` - Home insurance policies
- `life.md` - Life insurance policies

The system automatically indexes these documents using ColBERT for semantic search.

## Benefits of Modular Architecture

1. **Scalability**: Each component can be scaled independently
2. **Maintainability**: Clear separation of concerns
3. **Testability**: Individual components can be tested in isolation
4. **Flexibility**: Easy to swap out or upgrade individual components
5. **Monitoring**: Component-level health and performance tracking
6. **Reusability**: Components can be reused by other agents

## Dependencies

- `ragatouille` - For ColBERT-based retrieval
- `dspy` - For structured LLM interactions
- `eggai` - For agent framework and messaging
- `pydantic` - For type validation and settings

## Error Handling

The system includes comprehensive error handling:
- Component-level error isolation
- Automatic retry mechanisms
- Graceful degradation
- Detailed logging and tracing