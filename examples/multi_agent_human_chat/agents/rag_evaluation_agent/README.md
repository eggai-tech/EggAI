# RAG Evaluation Agent

The RAG Evaluation Agent is a monitoring and logging component that subscribes to messages from the RAG system components (retrieval, augmentation, and generation agents) and logs all interactions to a JSONL file for analysis and evaluation.

## Purpose

- **Message Monitoring**: Subscribes to internal channel messages from RAG components
- **Data Logging**: Logs all RAG-related messages to JSONL format for analysis
- **Performance Tracking**: Captures metrics like document counts, response lengths, and timing
- **Debugging Support**: Provides comprehensive message flow visibility

## Architecture

The agent subscribes to the internal channel and filters for these message types:

### Retrieval Agent Messages
- `retrieval_request` - Document retrieval requests
- `retrieval_response` - Retrieved documents and metadata

### Augmentation Agent Messages  
- `augmentation_request` - Context augmentation requests
- `augmentation_response` - Augmented context with metrics

### Generation Agent Messages
- `generation_request` - Response generation requests
- `generation_response` - Generated responses
- `generation_stream_start` - Streaming response start
- `generation_stream_chunk` - Streaming response chunks
- `generation_stream_end` - Streaming response end

## Log Format

Each log entry is stored as a JSON object in JSONL format with the following structure:

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "message_id": "unique-message-id",
  "message_type": "retrieval_response",
  "source": "RetrievalAgent", 
  "component": "retrieval_agent",
  "traceparent": "trace-id",
  "tracestate": "trace-state",
  "data": {
    "request_id": "req-123",
    "documents": [...]
  },
  "metrics": {
    "document_count": 5,
    "request_id": "req-123"
  }
}
```

## Usage

### Standalone Mode
```bash
python -m agents.rag_evaluation_agent.main
```

### Integrated Mode
Import and start the agent alongside other RAG components:

```python
from agents.rag_evaluation_agent.agent import rag_evaluation_agent

# Start with other agents
await rag_evaluation_agent.start()
```

## Log File Management

- **Location**: `logs/rag_evaluation/rag_messages_YYYYMMDD_HHMMSS.jsonl`
- **Format**: JSONL (one JSON object per line)
- **Rotation**: New file per agent startup with timestamp

## Utility Functions

- `get_log_file_path()` - Returns current log file path
- `get_log_stats()` - Returns log file statistics (size, line count, etc.)

## Integration with Knowledge Base Agent

The RAG Evaluation Agent is designed to work alongside the Knowledge Base Agent system. When the Knowledge Base Agent processes requests through its RAG pipeline, the evaluation agent automatically captures and logs all the interactions for later analysis.

## Analysis and Evaluation

The JSONL logs can be used for:
- **Performance Analysis**: Response times, document retrieval effectiveness
- **Quality Assessment**: Context augmentation quality, generation accuracy  
- **Debugging**: Message flow tracing, error analysis
- **Metrics Collection**: Usage patterns, system load analysis