"""
Constants for the Escalation Agent.

This module centralizes frequently used string literals to avoid typos
and make updates easier.
"""

# Agent identity
AGENT_NAME = "TicketingAgent"

# Message types
MSG_TYPE_TICKETING_REQUEST = "ticketing_request"

# Streaming message types for human_stream_channel
MSG_TYPE_STREAM_START = "agent_message_stream_start"
MSG_TYPE_STREAM_CHUNK = "agent_message_stream_chunk"
MSG_TYPE_STREAM_END = "agent_message_stream_end"

# Kafka consumer group ID for this agent
GROUP_ID = "escalation_agent_group"