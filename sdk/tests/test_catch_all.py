"""
Catch-all message handling test demonstrating graceful handling of unmatched messages.

This test verifies that:
- Agents can handle filtered messages correctly
- Unmatched messages don't cause system errors
- No SubscriberNotFound exceptions are raised for unhandled message types
"""

import asyncio
import uuid
from collections import defaultdict

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport


@pytest.mark.asyncio
async def test_catch_all(capfd):
    """
    Test graceful handling of messages when no handler matches.

    This scenario simulates a real-world case where:
    1. An agent handles specific message types (msg1)
    2. Other message types (msg2) may be published but have no dedicated handlers
    3. The system should handle this gracefully without errors

    The test verifies that unhandled messages don't cause SubscriberNotFound exceptions.
    """
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    message_processor = Agent(f"message-processor-{test_id}")
    event_channel = Channel(f"test-events-{test_id}")

    # Track message processing
    processed_messages = defaultdict(int)

    @message_processor.subscribe(
        event_channel, filter_by_message=lambda event: event.get("type") == "msg1"
    )
    async def handle_processed_message(event):
        """Handle messages of type 'msg1' and trigger a follow-up."""
        processed_messages["msg1"] += 1
        # Publish a follow-up message that may not have a handler
        await event_channel.publish({"type": "msg2"})

    # Start the message processing system
    await message_processor.start()

    # Publish a message that HAS a handler
    await event_channel.publish({"type": "msg1"})

    # Publish a message that has NO handler (should be handled gracefully)
    await event_channel.publish({"type": "msg2"})

    # Allow time for message processing
    await asyncio.sleep(0.5)
    await message_processor.stop()

    # Verify that handled messages were processed correctly
    assert processed_messages["msg1"] == 1, "Should process exactly one msg1"

    # Verify that no SubscriberNotFound exceptions occurred
    captured_output = capfd.readouterr()
    assert "SubscriberNotFound" not in captured_output.out, (
        "System should handle unmatched messages gracefully"
    )
