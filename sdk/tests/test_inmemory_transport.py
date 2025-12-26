"""
Example demonstrating in-memory transport with data_type and filter_by_data support.

This example shows how to use the InMemoryTransport with typed message subscriptions
and data filtering capabilities. It demonstrates:

1. Using data_type parameter to automatically parse and validate message types
2. Using filter_by_data to filter messages based on typed data content
3. How multiple handlers can process the same message with different filters

The InMemoryTransport is useful for testing and development environments where
you want message passing without external dependencies like Kafka.
"""

import asyncio
import uuid
from enum import Enum

from pydantic import BaseModel

from eggai import Agent, Channel
from eggai.schemas import BaseMessage
from eggai.transport import InMemoryTransport, eggai_set_default_transport


class OrderStatus(Enum):
    """Order status enumeration for demo purposes."""

    REQUESTED = "requested"
    CREATED = "created"
    PROCESSED = "processed"


class Order(BaseModel):
    """Order data model."""

    order_id: int
    user_id: str
    amount: float
    status: OrderStatus


class OrderMessage(BaseMessage[Order]):
    """Typed message wrapper for Order data."""

    type: str = "OrderMessage"


async def demo_inmemory_transport_with_filters():
    """
    Demonstrates in-memory transport with data_type and filter_by_data functionality.

    This example creates two handlers:
    1. A general handler that receives all OrderMessage instances
    2. A filtered handler that only receives orders with REQUESTED status

    Both handlers receive typed OrderMessage objects and can access the typed data
    through the .data attribute.
    """
    # Configure the transport to use in-memory implementation
    eggai_set_default_transport(lambda: InMemoryTransport())

    # Create agent and channel
    test_id = uuid.uuid4().hex[:8]
    agent = Agent(f"test-inmemory-demo-agent-{test_id}")
    channel = Channel(f"test-inmemory-demo-{test_id}")

    # Track handler invocations for demonstration
    handler_calls = {}
    processed_orders = []

    def track_call(handler_name: str):
        """Helper to track handler invocations."""
        handler_calls[handler_name] = handler_calls.get(handler_name, 0) + 1

    def store_order(order: Order):
        """Helper to store processed orders."""
        processed_orders.append(order)

    @agent.subscribe(data_type=OrderMessage, channel=channel)
    async def handle_all_orders(order: OrderMessage):
        """
        Handler that processes all OrderMessage instances.

        Args:
            order: The typed OrderMessage containing Order data
        """
        # Process order (in real system: validate, update inventory, etc.)
        track_call("all_orders")
        store_order(order.data)

    @agent.subscribe(
        data_type=OrderMessage,
        channel=channel,
        filter_by_data=lambda order: order.data.status == OrderStatus.REQUESTED,
    )
    async def handle_requested_orders(order: OrderMessage):
        """
        Handler that only processes orders with REQUESTED status.

        The filter_by_data parameter receives the typed OrderMessage object
        and can access its data to make filtering decisions.

        Args:
            order: The typed OrderMessage containing Order data
        """
        # Handle new order request (in real system: validate, approve, etc.)
        track_call("requested_orders")
        # Could trigger additional processing here, like validation or approval workflow

    # Start the agent to begin processing messages
    await agent.start()

    # Publish test messages to demonstrate filtering

    # This order should trigger both handlers (all_orders + requested_orders)
    await channel.publish(
        OrderMessage(
            source="order-service",
            data=Order(
                order_id=1001,
                user_id="user123",
                amount=99.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    # This order should only trigger the all_orders handler
    await channel.publish(
        OrderMessage(
            source="fulfillment-service",
            data=Order(
                order_id=1002,
                user_id="user456",
                amount=149.99,
                status=OrderStatus.PROCESSED,
            ),
        )
    )

    # Allow time for message processing
    await asyncio.sleep(0.1)

    # Display results
    # Verify the results demonstrate proper filtering behavior

    # Verify expected behavior
    assert handler_calls.get("all_orders") == 2, (
        "All orders handler should be called twice"
    )
    assert handler_calls.get("requested_orders") == 1, (
        "Requested orders handler should be called once"
    )
    assert len(processed_orders) == 2, "Should have processed 2 orders total"

    # Clean up
    await agent.stop()
    # Demo completed successfully - all assertions passed


if __name__ == "__main__":
    """Run the demo when executed directly."""
    print("EggAI In-Memory Transport Demo")
    print("=" * 40)
    asyncio.run(demo_inmemory_transport_with_filters())
