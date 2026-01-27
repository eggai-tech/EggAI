"""
Redis transport integration tests demonstrating core messaging functionality.

This test suite verifies:
- Basic Redis transport operation with EggAI agents
- Event-driven message flows (request -> response patterns)
- Channel-based message routing and isolation
- Direct channel subscription patterns
"""

import asyncio
import uuid

import pytest
import redis.asyncio as redis

from eggai import Agent, Channel
from eggai.transport import RedisTransport, eggai_set_default_transport


@pytest.mark.asyncio
async def test_redis(capfd):
    """
    Test basic Redis transport functionality with event-driven message flow.

    This demonstrates a common microservices pattern:
    1. External request triggers "order_requested" event
    2. Order service processes request and publishes "order_created" event
    3. Both events are handled by appropriate handlers

    This pattern is useful for decoupled, event-driven architectures.
    """
    eggai_set_default_transport(lambda: RedisTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    order_service = Agent(f"order-service-{test_id}")
    order_events = Channel(f"test-order-events-{test_id}")

    # Track event processing
    events_processed = {}

    def track_event_processing(event_type: str):
        """Track which events have been processed."""
        events_processed[event_type] = events_processed.get(event_type, 0) + 1

    @order_service.subscribe(
        channel=order_events,
        filter_by_message=lambda msg: msg.get("type") == "order_requested",
    )
    async def handle_order_request(message):
        """
        Process incoming order requests and trigger order creation.

        In a real system, this might validate the order, check inventory,
        calculate pricing, etc., before confirming the order creation.
        """
        track_event_processing("order_requested")

        # Simulate order processing and publish follow-up event
        await order_events.publish(
            {
                "type": "order_created",
                "order_id": message.get("order_id", "unknown"),
                "status": "confirmed",
            }
        )

    @order_service.subscribe(
        channel=order_events,
        filter_by_message=lambda msg: msg.get("type") == "order_created",
    )
    async def handle_order_created(message):
        """
        Handle order creation confirmation events.

        This might trigger fulfillment, send confirmation emails,
        update inventory, etc.
        """
        track_event_processing("order_created")

    # Start the order processing system
    await order_service.start()

    # Simulate an order request from a customer
    await order_events.publish(
        {
            "type": "order_requested",
            "order_id": "ORD-12345",
            "customer_id": "CUST-789",
            "items": [{"product": "laptop", "quantity": 1}],
        }
    )

    # Allow time for message processing
    await asyncio.sleep(0.5)
    await order_service.stop()

    # Verify the event flow worked correctly
    assert events_processed.get("order_requested") == 1, (
        "Should process the order request"
    )
    assert events_processed.get("order_created") == 1, (
        "Should process the order creation event"
    )


@pytest.mark.asyncio
async def test_channel_subscribe_multiple():
    """
    Test multiple channel subscriptions and message routing.

    This demonstrates how channels provide message isolation:
    - Multiple subscribers to the same channel all receive messages
    - Different channels maintain separate message streams
    - Useful for fan-out patterns and service isolation
    """
    eggai_set_default_transport(lambda: RedisTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    user_events = Channel(name=f"test-user-events-{test_id}")
    user_events_copy = Channel(name=f"test-user-events-{test_id}")  # Same channel name
    system_events = Channel(name=f"test-system-events-{test_id}")  # Different channel

    # Track messages received by different subscribers
    user_event_subscribers = []
    system_event_subscribers = []

    # Subscribe multiple handlers to the same channel (fan-out pattern)
    await user_events.subscribe(
        lambda event: user_event_subscribers.append(("analytics_service", event))
    )
    await user_events_copy.subscribe(
        lambda event: user_event_subscribers.append(("notification_service", event))
    )

    # Subscribe to a different channel
    await system_events.subscribe(lambda event: system_event_subscribers.append(event))

    # Publish to user events channel
    await user_events.publish(
        {
            "event": "user_login",
            "user_id": "user123",
            "timestamp": "2024-01-01T10:00:00Z",
        }
    )
    await asyncio.sleep(0.5)

    # Both subscribers to user_events should receive the message
    assert len(user_event_subscribers) == 2, (
        f"Expected 2 subscribers to receive user event, got {len(user_event_subscribers)}"
    )

    # Publish to system events channel
    await system_events.publish(
        {
            "event": "server_health_check",
            "status": "healthy",
            "timestamp": "2024-01-01T10:01:00Z",
        }
    )
    await asyncio.sleep(0.5)

    # Only system events subscriber should receive this message
    assert len(system_event_subscribers) == 1, (
        f"Expected 1 subscriber to receive system event, got {len(system_event_subscribers)}"
    )


@pytest.mark.asyncio
async def test_redis_no_ack_on_error():
    """
    Test that messages are NOT acknowledged when handler raises an exception.

    This is critical for reliability:
    - When a handler fails, the message should remain in the Pending Entries List (PEL)
    - The message should be available for redelivery (either to same or different consumer)
    - This ensures no message loss during transient failures

    The test verifies:
    1. First consumer: Handler raises exception -> message NOT acked
    2. Message remains in PEL (verified via Redis XPENDING command)
    3. Second consumer with min_idle_time claims and processes the message
    """

    # Create Redis client to inspect PEL directly
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    test_id = uuid.uuid4().hex[:8]
    channel_name = f"test-error-channel-{test_id}"
    stream_name = f"eggai.{channel_name}"

    # --- Phase 1: First consumer that will fail ---
    transport1 = RedisTransport()
    agent1 = Agent(f"failing-agent-{test_id}", transport=transport1)
    channel1 = Channel(channel_name, transport=transport1)

    first_attempt_done = asyncio.Event()

    class TransientError(Exception):
        """Simulates a transient error that should trigger retry."""

        pass

    @agent1.subscribe(channel=channel1)
    async def failing_handler(message):
        """Handler that always fails."""
        first_attempt_done.set()
        raise TransientError("Simulated transient error")

    await agent1.start()

    # Publish a message
    await channel1.publish(
        {
            "type": "test_message",
            "data": "should_be_retried",
            "test_id": test_id,
        }
    )

    # Wait for first attempt to complete
    await asyncio.wait_for(first_attempt_done.wait(), timeout=5.0)

    # Give time for the nack to be processed
    await asyncio.sleep(0.3)

    # Stop the first agent
    await agent1.stop()

    # Check that message is in the Pending Entries List (PEL)
    # The handler_id format is: {agent_name}-{handler_func_name}-{counter}
    group_name = f"failing-agent-{test_id}-failing_handler-1"
    pending_count = -1
    try:
        pending_info = await redis_client.xpending(stream_name, group_name)
        pending_count = (
            pending_info.get("pending", 0)
            if isinstance(pending_info, dict)
            else pending_info[0]
        )
    except Exception as e:
        print(f"Error checking pending: {e}")

    # --- Phase 2: Second consumer that claims and succeeds ---
    transport2 = RedisTransport()
    agent2 = Agent(f"recovery-agent-{test_id}", transport=transport2)
    channel2 = Channel(channel_name, transport=transport2)

    recovered_messages = []
    recovery_done = asyncio.Event()

    @agent2.subscribe(
        channel=channel2,
        # Use the same consumer group as the failed agent to claim its pending messages
        group=group_name,
        # Enable auto-claiming of pending messages after 100ms idle time
        min_idle_time=100,
    )
    async def recovery_handler(message):
        """Handler that successfully processes claimed messages."""
        recovered_messages.append(message)
        recovery_done.set()

    await agent2.start()

    # Wait for recovery
    try:
        await asyncio.wait_for(recovery_done.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pass

    await agent2.stop()
    await redis_client.aclose()

    # Verify behavior
    assert pending_count >= 1, (
        f"Expected at least 1 pending message after error, got {pending_count}. "
        "This suggests messages ARE being acked on error (incorrect behavior)."
    )
    assert len(recovered_messages) == 1, (
        f"Expected recovery agent to process 1 message, got {len(recovered_messages)}. "
        "Message was either acked on error or not properly claimed."
    )
