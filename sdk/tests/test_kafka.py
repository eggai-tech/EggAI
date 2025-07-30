"""
Kafka transport integration tests demonstrating core messaging functionality.

This test suite verifies:
- Basic Kafka transport operation with EggAI agents
- Event-driven message flows (request -> response patterns)
- Channel-based message routing and isolation
- Direct channel subscription patterns
"""

import asyncio
import uuid

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport


@pytest.mark.asyncio
async def test_kafka(capfd):
    """
    Test basic Kafka transport functionality with event-driven message flow.
    
    This demonstrates a common microservices pattern:
    1. External request triggers "order_requested" event
    2. Order service processes request and publishes "order_created" event  
    3. Both events are handled by appropriate handlers
    
    This pattern is useful for decoupled, event-driven architectures.
    """
    eggai_set_default_transport(lambda: KafkaTransport())
    
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
        filter_by_message=lambda msg: msg.get("type") == "order_requested"
    )
    async def handle_order_request(message):
        """
        Process incoming order requests and trigger order creation.
        
        In a real system, this might validate the order, check inventory,
        calculate pricing, etc., before confirming the order creation.
        """
        track_event_processing("order_requested")
        
        # Simulate order processing and publish follow-up event
        await order_events.publish({
            "type": "order_created",
            "order_id": message.get("order_id", "unknown"),
            "status": "confirmed"
        })

    @order_service.subscribe(
        channel=order_events,
        filter_by_message=lambda msg: msg.get("type") == "order_created"
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
    await order_events.publish({
        "type": "order_requested",
        "order_id": "ORD-12345",
        "customer_id": "CUST-789",
        "items": [{"product": "laptop", "quantity": 1}]
    })
    
    # Allow time for message processing
    await asyncio.sleep(0.5)
    await order_service.stop()
    
    # Verify the event flow worked correctly
    assert events_processed.get("order_requested") == 1, \
        "Should process the order request"
    assert events_processed.get("order_created") == 1, \
        "Should process the order creation event"


@pytest.mark.asyncio
async def test_channel_subscribe_multiple():
    """
    Test multiple channel subscriptions and message routing.
    
    This demonstrates how channels provide message isolation:
    - Multiple subscribers to the same channel all receive messages
    - Different channels maintain separate message streams  
    - Useful for fan-out patterns and service isolation
    """
    eggai_set_default_transport(lambda: KafkaTransport())
    
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
    await system_events.subscribe(
        lambda event: system_event_subscribers.append(event)
    )

    # Publish to user events channel
    await user_events.publish({
        "event": "user_login", 
        "user_id": "user123",
        "timestamp": "2024-01-01T10:00:00Z"
    })
    await asyncio.sleep(0.5)
    
    # Both subscribers to user_events should receive the message
    assert len(user_event_subscribers) == 2, \
        f"Expected 2 subscribers to receive user event, got {len(user_event_subscribers)}"

    # Publish to system events channel  
    await system_events.publish({
        "event": "server_health_check",
        "status": "healthy",
        "timestamp": "2024-01-01T10:01:00Z"
    })
    await asyncio.sleep(0.5)
    
    # Only system events subscriber should receive this message
    assert len(system_event_subscribers) == 1, \
        f"Expected 1 subscriber to receive system event, got {len(system_event_subscribers)}"
