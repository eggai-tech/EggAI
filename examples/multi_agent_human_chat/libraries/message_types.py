from enum import Enum


class MessageType(str, Enum):
    """Centralized message type definitions used across all agents."""
    
    # User interactions
    USER_MESSAGE = "user_message"
    
    # Agent requests
    BILLING_REQUEST = "billing_request"
    CLAIM_REQUEST = "claim_request"
    POLICY_REQUEST = "policy_request"
    TICKETING_REQUEST = "ticketing_request"
    ESCALATION_REQUEST = "escalation_request"
    TRIAGE_REQUEST = "triage_request"
    
    # Agent responses
    AGENT_MESSAGE = "agent_message"
    
    # Streaming messages
    AGENT_MESSAGE_STREAM_START = "agent_message_stream_start"
    AGENT_MESSAGE_STREAM_CHUNK = "agent_message_stream_chunk"
    AGENT_MESSAGE_STREAM_END = "agent_message_stream_end"
    AGENT_MESSAGE_STREAM_WAITING = "agent_message_stream_waiting_message"