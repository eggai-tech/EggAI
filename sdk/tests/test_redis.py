"""
Redis transport integration tests demonstrating core messaging functionality.

This test suite verifies:
- Basic Redis transport operation with EggAI agents
- Event-driven message flows (request -> response patterns)
- Channel-based message routing and isolation
- Direct channel subscription patterns
"""

import asyncio
import logging
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


@pytest.mark.asyncio
async def test_retry_on_idle_ms_basic():
    """
    Test SDK-managed PEL reclaiming via retry_on_idle_ms.

    Flow:
      1. Handler raises on the first call (message stays in PEL).
      2. Reclaimer fires after retry_on_idle_ms and moves the message to the
         .retry stream.
      3. The same handler processes the message from the retry stream and succeeds.

    Asserts:
      - Handler is invoked exactly twice (once on main, once on retry).
      - No duplicate: only one unique message payload received.
      - PEL on main stream is empty after retry succeeds.
      - PEL on retry stream is empty after retry succeeds.
    """
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    test_id = uuid.uuid4().hex[:8]
    channel_name = f"test-retry-idle-{test_id}"
    stream_name = f"eggai.{channel_name}"
    retry_stream_name = f"{stream_name}.retry"

    transport = RedisTransport()
    agent = Agent(f"retry-agent-{test_id}", transport=transport)
    channel = Channel(channel_name, transport=transport)

    call_count = 0
    received_payloads = []
    retry_done = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=500,
        retry_reclaim_interval_s=1.0,
    )
    async def handler(message):
        nonlocal call_count
        call_count += 1
        received_payloads.append(message.get("data"))
        if call_count == 1:
            raise RuntimeError("transient failure")
        retry_done.set()

    await agent.start()

    await channel.publish({"type": "test", "data": "hello", "test_id": test_id})

    # Wait for the retry handler to succeed (reclaimer fires after ~1s).
    await asyncio.wait_for(retry_done.wait(), timeout=10.0)
    # Brief pause so XACK can complete.
    await asyncio.sleep(0.3)

    await agent.stop()

    # Determine group names (mirrors agent.py handler_id format).
    group_main = f"retry-agent-{test_id}-handler-1"
    group_retry = f"{group_main}-retry"

    def get_pending(info):
        return info.get("pending", 0) if isinstance(info, dict) else info[0]

    pending_main = get_pending(await redis_client.xpending(stream_name, group_main))
    pending_retry = get_pending(
        await redis_client.xpending(retry_stream_name, group_retry)
    )

    await redis_client.aclose()

    assert call_count == 2, f"Expected 2 handler calls, got {call_count}"
    assert received_payloads == ["hello", "hello"], (
        f"Unexpected payloads: {received_payloads}"
    )
    assert pending_main == 0, f"Main PEL not empty after retry: {pending_main} pending"
    assert pending_retry == 0, (
        f"Retry PEL not empty after success: {pending_retry} pending"
    )


@pytest.mark.asyncio
async def test_retry_on_idle_ms_no_retry_retry_stream():
    """
    Persistent failure in the retry handler must NOT create a .retry.retry stream.
    The retry-stream reclaimer re-queues back to the same retry stream.

    Asserts:
      - No stream named eggai.{channel}.retry.retry is ever created.
      - The retry handler is called multiple times (reclaimer keeps requeueing).
    """
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    test_id = uuid.uuid4().hex[:8]
    channel_name = f"test-no-retry-retry-{test_id}"
    retry_retry_stream = f"eggai.{channel_name}.retry.retry"

    transport = RedisTransport()
    agent = Agent(f"persistent-fail-agent-{test_id}", transport=transport)
    channel = Channel(channel_name, transport=transport)

    call_count = 0
    second_retry_seen = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=300,
        retry_reclaim_interval_s=0.5,
    )
    async def always_failing_handler(message):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            second_retry_seen.set()
        raise RuntimeError("persistent failure")

    await agent.start()

    await channel.publish({"type": "test", "data": "will-fail", "test_id": test_id})

    # Wait long enough for at least two reclaim cycles.
    await asyncio.wait_for(second_retry_seen.wait(), timeout=15.0)

    await agent.stop()

    retry_retry_exists = await redis_client.exists(retry_retry_stream)
    await redis_client.aclose()

    assert retry_retry_exists == 0, (
        f"A .retry.retry stream was created: {retry_retry_stream}"
    )
    assert call_count >= 3, (
        f"Expected handler to be called at least 3 times, got {call_count}"
    )


@pytest.mark.asyncio
async def test_retry_on_idle_ms_conflict_with_min_idle_time():
    """Setting both min_idle_time and retry_on_idle_ms must raise ValueError."""
    transport = RedisTransport()
    agent = Agent("conflict-agent", transport=transport)
    channel = Channel("test-conflict-channel", transport=transport)

    with pytest.raises(ValueError, match="mutually exclusive"):

        @agent.subscribe(channel=channel, min_idle_time=100, retry_on_idle_ms=500)
        async def handler(message):
            pass


@pytest.mark.asyncio
async def test_retry_on_idle_ms_uses_prefixed_stream_keys():
    """Reclaimer configs must target the actual Redis stream keys used by FastStream."""
    transport = RedisTransport()

    async def handler(message):
        return message

    await transport.subscribe(
        "orders",
        handler,
        handler_id="orders-handler-1",
        retry_on_idle_ms=500,
    )

    assert transport._reclaimer_manager is not None

    configs = sorted(
        transport._reclaimer_manager._configs.values(),
        key=lambda config: config.stream,
    )

    assert len(configs) == 2
    assert configs[0].stream == "eggai.orders"
    assert configs[0].retry_stream == "eggai.orders.retry"
    assert configs[1].stream == "eggai.orders.retry"
    assert configs[1].retry_stream == "eggai.orders.retry"


@pytest.mark.asyncio
async def test_retry_on_idle_ms_metadata():
    """
    Verify that _retry_count and _original_message_id are injected into the
    message fields when it is delivered via the retry stream.
    """
    test_id = uuid.uuid4().hex[:8]
    channel_name = f"test-retry-meta-{test_id}"

    transport = RedisTransport()
    agent = Agent(f"meta-agent-{test_id}", transport=transport)
    channel = Channel(channel_name, transport=transport)

    call_count = 0
    retry_fields: dict = {}
    retry_done = asyncio.Event()

    @agent.subscribe(
        channel=channel,
        retry_on_idle_ms=300,
        retry_reclaim_interval_s=0.5,
    )
    async def handler(message):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first attempt fails")
        retry_fields.update(message)
        retry_done.set()

    await agent.start()
    await channel.publish({"type": "test", "data": "check-meta", "test_id": test_id})

    await asyncio.wait_for(retry_done.wait(), timeout=10.0)
    await agent.stop()

    assert "_retry_count" in retry_fields, "Missing _retry_count in retry delivery"
    assert retry_fields["_retry_count"] == "1", (
        f"Expected _retry_count='1', got {retry_fields.get('_retry_count')!r}"
    )
    assert "_original_message_id" in retry_fields, (
        "Missing _original_message_id in retry delivery"
    )


@pytest.mark.asyncio
async def test_inject_retry_metadata_malformed_payload(caplog):
    """_inject_retry_metadata logs a warning and returns data unchanged for unparseable input."""
    from eggai.transport.pending_reclaimer import _inject_retry_metadata

    garbage = b"\x00\x01\x02not-valid-binary-format"
    with caplog.at_level(logging.WARNING, logger="eggai.transport.pending_reclaimer"):
        result = _inject_retry_metadata(garbage, "0-1")
    assert result == garbage
    assert any("Failed to inject retry metadata" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_reclaimer_manager_start_stop_cycles():
    """PendingReclaimerManager handles repeated start/stop without leaking clients."""
    from eggai.transport.pending_reclaimer import (
        PendingReclaimerManager,
        ReclaimerConfig,
    )

    manager = PendingReclaimerManager("redis://localhost:6379")
    assert manager._redis_client is None

    manager.add(
        ReclaimerConfig(
            stream="test-stream",
            group="test-group",
            consumer="test-consumer",
            retry_stream="test-stream.retry",
            min_idle_ms=60_000,
            interval_s=60.0,
        )
    )

    # First cycle
    await manager.start()
    assert manager._redis_client is not None
    await manager.stop()
    assert manager._redis_client is None

    # Second cycle — must not raise or leak the previous client
    await manager.start()
    assert manager._redis_client is not None
    await manager.stop()
    assert manager._redis_client is None


@pytest.mark.asyncio
async def test_reclaimer_manager_stop_without_start():
    """Calling stop() before start() must not raise."""
    from eggai.transport.pending_reclaimer import PendingReclaimerManager

    manager = PendingReclaimerManager("redis://localhost:6379")
    await manager.stop()  # should not raise
