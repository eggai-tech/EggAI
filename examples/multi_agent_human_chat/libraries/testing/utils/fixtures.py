import asyncio
import time
from typing import Dict, List, Optional

from libraries.observability.logger import get_console_logger

logger = get_console_logger("test_utils.fixtures")


def create_message_list(
    user_messages: List[str], 
    agent_responses: Optional[List[str]] = None,
    user_role: str = "User",
    agent_role: str = "Agent"
) -> List[Dict[str, str]]:
    if agent_responses is None:
        agent_responses = []

    messages = []
    for i, user_msg in enumerate(user_messages):
        messages.append({"role": user_role, "content": user_msg})
        if i < len(agent_responses):
            messages.append({"role": agent_role, "content": agent_responses[i]})
    return messages


def create_conversation_string(messages: List[Dict[str, str]]) -> str:
    conversation = ""
    for msg in messages:
        conversation += f"{msg['role']}: {msg['content']}\n"
    return conversation


async def wait_for_agent_response(
    response_queue: asyncio.Queue,
    connection_id: str,
    timeout: float = 30.0,
    expected_source: Optional[str] = None
) -> dict:
    start_wait = time.perf_counter()
    logger.info(f"Waiting for response with connection_id {connection_id}")

    while not response_queue.empty():
        try:
            old_event = response_queue.get_nowait()
            logger.info(
                f"Cleared old response: {old_event.get('source', 'unknown')} for "
                f"{old_event.get('data', {}).get('connection_id', 'unknown')}"
            )
        except asyncio.QueueEmpty:
            break

    # Keep checking for matching responses
    while (time.perf_counter() - start_wait) < timeout:
        try:
            # Use a shorter timeout for the queue get to check more frequently
            event = await asyncio.wait_for(response_queue.get(), timeout=1.0)

            logger.info(
                f"Received event from {event.get('source', 'unknown')} for "
                f"connection {event.get('data', {}).get('connection_id', 'unknown')}"
            )

            # Check if this response matches our request
            event_connection_id = event.get("data", {}).get("connection_id")
            event_source = event.get("source")
            
            if event_connection_id == connection_id:
                # If expected_source is specified, check it matches
                if expected_source is None or event_source == expected_source:
                    logger.info(f"Found matching response for {connection_id}")
                    return event
                else:
                    logger.info(
                        f"Connection ID matches but source doesn't: "
                        f"expected {expected_source}, got {event_source}"
                    )
            else:
                logger.info(
                    f"Received non-matching response: {event_source} for "
                    f"{event_connection_id}"
                )
        except asyncio.TimeoutError:
            # Wait a little and try again but don't log every attempt
            await asyncio.sleep(0.1)

        # Regularly report waiting status
        if (time.perf_counter() - start_wait) % 5 < 0.1:
            logger.info(
                f"Still waiting for response from {expected_source or 'any agent'} "
                f"for connection {connection_id}..."
            )

    logger.error(
        f"Timeout after {timeout}s waiting for response with connection_id {connection_id}"
    )
    raise asyncio.TimeoutError(
        f"Timeout waiting for response with connection_id {connection_id}"
    )