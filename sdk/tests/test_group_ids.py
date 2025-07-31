"""
Consumer group functionality tests demonstrating Kafka-style message distribution patterns.

This test suite showcases three key messaging patterns:
1. Multiple consumer groups - each group gets a copy of every message
2. Load balancing within groups - messages distributed among group members
3. Broadcasting without groups - all subscribers get every message
"""

import asyncio
import uuid

import pytest

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport


@pytest.mark.asyncio
async def test_group_ids(capfd):
    """
    Test multiple consumer groups receiving the same message.

    This demonstrates the fundamental consumer group pattern where:
    - Each consumer group receives a copy of every message
    - Different groups can process the same message independently
    - Useful for scenarios like: logging, analytics, and business logic
      all processing the same events independently
    """
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    order_channel = Channel(f"test-order-events-{test_id}")
    order_processor = Agent(f"order-processor-{test_id}")

    # Track which groups processed messages
    group_activity = {}

    def track_group_activity(group_name: str):
        """Track activity per consumer group."""
        group_activity[group_name] = group_activity.get(group_name, 0) + 1

    @order_processor.subscribe(
        channel=order_channel,
        filter_by_message=lambda event: event["type"] == 1,
        group_id="analytics_group",  # Analytics service group
    )
    async def analytics_handler(event):
        """Process order events for analytics purposes."""
        track_group_activity("analytics")

    @order_processor.subscribe(
        channel=order_channel,
        filter_by_message=lambda event: event["type"] == 1,
        group_id="fulfillment_group",  # Order fulfillment group
    )
    async def fulfillment_handler(event):
        """Process order events for fulfillment purposes."""
        track_group_activity("fulfillment")

    await order_processor.start()

    # Publish one order event
    await order_channel.publish({"type": 1, "order_id": "ORDER-123"})
    await asyncio.sleep(0.5)
    await order_processor.stop()

    # Both consumer groups should receive the same message
    assert group_activity.get("analytics") == 1, (
        "Analytics group should process the order"
    )
    assert group_activity.get("fulfillment") == 1, (
        "Fulfillment group should process the order"
    )


@pytest.mark.asyncio
async def test_2_agents_same_group(capfd):
    """
    Test load balancing within a single consumer group.

    This demonstrates how multiple agents in the same consumer group
    share the workload - only one agent processes each message.
    This is useful for horizontal scaling where you have multiple
    instances of the same service.
    """
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    work_channel = Channel(f"test-work-queue-{test_id}")
    worker_1 = Agent(f"worker-1-{test_id}")
    worker_2 = Agent(f"worker-2-{test_id}")

    # Track total work processed (should be exactly 1)
    work_processed = {}

    def track_work_processed(worker_id: str):
        """Track work processed across all workers in the group."""
        work_processed["total"] = work_processed.get("total", 0) + 1
        work_processed["by_worker"] = work_processed.get("by_worker", [])
        work_processed["by_worker"].append(worker_id)

    @worker_1.subscribe(
        channel=work_channel,
        filter_by_message=lambda event: event["type"] == 2,
        group_id="worker_pool",  # Both workers in same group
    )
    async def worker_1_handler(event):
        """Worker 1 processing logic."""
        track_work_processed("worker_1")

    @worker_2.subscribe(
        channel=work_channel,
        filter_by_message=lambda event: event["type"] == 2,
        group_id="worker_pool",  # Both workers in same group
    )
    async def worker_2_handler(event):
        """Worker 2 processing logic."""
        track_work_processed("worker_2")

    await worker_1.start()
    await worker_2.start()

    # Send one work item
    await work_channel.publish({"type": 2, "task_id": "TASK-456"})
    await asyncio.sleep(4)  # Allow time for consumer group coordination

    await worker_1.stop()
    await worker_2.stop()

    # Only one worker should have processed the message due to load balancing
    assert work_processed.get("total") == 1, (
        "Exactly one worker should process the message in a consumer group"
    )


@pytest.mark.asyncio
async def test_broadcasting(capfd):
    """
    Test broadcasting to all subscribers without consumer groups.

    This demonstrates the broadcast pattern where every subscriber
    receives every message. This is useful for notifications,
    real-time updates, or event broadcasting scenarios.
    """
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create isolated test resources
    test_id = uuid.uuid4().hex[:8]
    notification_channel = Channel(f"test-notifications-{test_id}")
    mobile_app = Agent(f"mobile-app-{test_id}")
    web_app = Agent(f"web-app-{test_id}")

    # Track notifications received by each app
    notifications_received = {}

    def track_notification(app_name: str):
        """Track notifications received by each application."""
        notifications_received[app_name] = notifications_received.get(app_name, 0) + 1

    @mobile_app.subscribe(
        channel=notification_channel,
        filter_by_message=lambda event: event["type"] == 3,
        # No group_id = broadcasting mode - each subscriber gets the message
    )
    async def mobile_notification_handler(event):
        """Handle notifications for mobile app users."""
        track_notification("mobile_app")

    @web_app.subscribe(
        channel=notification_channel,
        filter_by_message=lambda event: event["type"] == 3,
        # No group_id = broadcasting mode - each subscriber gets the message
    )
    async def web_notification_handler(event):
        """Handle notifications for web app users."""
        track_notification("web_app")

    await mobile_app.start()
    await web_app.start()

    # Send a notification
    await notification_channel.publish(
        {"type": 3, "message": "System maintenance in 10 minutes"}
    )
    await asyncio.sleep(0.5)

    await mobile_app.stop()
    await web_app.stop()

    # Both applications should receive the broadcast notification
    assert notifications_received.get("mobile_app") == 1, (
        "Mobile app should receive the broadcast notification"
    )
    assert notifications_received.get("web_app") == 1, (
        "Web app should receive the broadcast notification"
    )
