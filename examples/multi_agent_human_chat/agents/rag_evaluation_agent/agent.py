import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from eggai import Agent, Channel

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler

rag_evaluation_agent = Agent(name="RagEvaluationAgent")
logger = get_console_logger("rag_evaluation_agent")
tracer = create_tracer("rag_evaluation_agent")
internal_channel = Channel(channels.internal)

# Configure log file path
LOG_DIR = Path("logs/rag_evaluation")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"rag_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"


def log_message_to_jsonl(message_data: Dict[str, Any]) -> None:
    """Log message data to JSONL file."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            json.dump(message_data, f, default=str, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to write to JSONL log: {e}")


@rag_evaluation_agent.subscribe(
    channel=internal_channel,
    filter_by_message=lambda msg: msg.get("type") in [
        "retrieval_request",
        "retrieval_response", 
        "augmentation_request",
        "augmentation_response",
        "generation_request",
        "generation_response",
        "generation_stream_start",
        "generation_stream_chunk",
        "generation_stream_end"
    ],
    auto_offset_reset="latest",
    group_id="rag_evaluation_agent_group",
)
@traced_handler("handle_rag_messages")
async def handle_rag_messages(msg: TracedMessage) -> None:
    """Handle and log messages from RAG components."""
    try:
        timestamp = datetime.now().isoformat()
        
        # Extract relevant data from the message
        log_entry = {
            "timestamp": timestamp,
            "message_id": str(msg.id) if hasattr(msg, 'id') else None,
            "message_type": msg.type,
            "source": msg.source,
            "traceparent": msg.traceparent,
            "tracestate": msg.tracestate,
            "data": msg.data
        }
        
        # Add component-specific metadata
        if msg.type.startswith("retrieval"):
            log_entry["component"] = "retrieval_agent"
            if msg.type == "retrieval_response":
                documents = msg.data.get("documents", [])
                log_entry["metrics"] = {
                    "document_count": len(documents),
                    "request_id": msg.data.get("request_id")
                }
        elif msg.type.startswith("augmentation"):
            log_entry["component"] = "augmentation_agent"
            if msg.type == "augmentation_response":
                log_entry["metrics"] = {
                    "augmented_context_length": len(msg.data.get("augmented_context", "")),
                    "document_count": msg.data.get("document_count", 0),
                    "request_id": msg.data.get("request_id")
                }
        elif msg.type.startswith("generation"):
            log_entry["component"] = "generation_agent"
            if msg.type == "generation_response":
                log_entry["metrics"] = {
                    "response_length": len(msg.data.get("response", "")),
                    "request_id": msg.data.get("request_id")
                }
            elif msg.type == "generation_stream_chunk":
                log_entry["metrics"] = {
                    "chunk_length": len(msg.data.get("chunk", "")),
                    "chunk_index": msg.data.get("chunk_index"),
                    "request_id": msg.data.get("request_id")
                }
        
        # Log to JSONL file
        log_message_to_jsonl(log_entry)
        
        logger.info(f"Logged {msg.type} message from {msg.source}")
        
    except Exception as e:
        logger.error(f"Error handling RAG message: {e}", exc_info=True)


@rag_evaluation_agent.subscribe(
    channel=internal_channel,
    auto_offset_reset="latest", 
    group_id="rag_evaluation_debug_group",
)
@traced_handler("handle_all_internal_messages")
async def handle_all_internal_messages(msg: TracedMessage) -> None:
    """Debug handler to log all internal channel messages."""
    try:
        # Only log if it's not already handled by the main handler
        if msg.type not in [
            "retrieval_request", "retrieval_response",
            "augmentation_request", "augmentation_response", 
            "generation_request", "generation_response",
            "generation_stream_start", "generation_stream_chunk", "generation_stream_end"
        ]:
            timestamp = datetime.now().isoformat()
            debug_entry = {
                "timestamp": timestamp,
                "message_type": msg.type,
                "source": msg.source,
                "category": "debug_other",
                "data_keys": list(msg.data.keys()) if msg.data else []
            }
            log_message_to_jsonl(debug_entry)
            logger.debug(f"Debug logged {msg.type} from {msg.source}")
            
    except Exception as e:
        logger.error(f"Error in debug message handler: {e}", exc_info=True)


def get_log_file_path() -> str:
    """Return the current log file path."""
    return str(LOG_FILE)


def get_log_stats() -> Dict[str, Any]:
    """Get statistics about the current log file."""
    try:
        if not LOG_FILE.exists():
            return {"exists": False, "size": 0, "line_count": 0}
            
        stat = LOG_FILE.stat()
        line_count = 0
        with open(LOG_FILE, "r") as f:
            line_count = sum(1 for _ in f)
            
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "line_count": line_count,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "path": str(LOG_FILE)
        }
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    logger.info(f"RAG Evaluation Agent logging to: {LOG_FILE}")
    logger.info("Use get_log_file_path() and get_log_stats() for log file information")
    
    # Test logging functionality
    test_entry = {
        "timestamp": datetime.now().isoformat(),
        "message_type": "test",
        "source": "rag_evaluation_agent_test",
        "data": {"test": True}
    }
    log_message_to_jsonl(test_entry)
    logger.info("Test log entry written successfully")