"""
Typed message subscription tests demonstrating strongly-typed message handling.

This test suite showcases EggAI's advanced typed messaging features:
- data_type parameter for automatic message type validation and parsing
- filter_by_data for filtering on typed message content
- Type-safe message handlers with Pydantic models
- Automatic BaseMessage wrapping and unwrapping
"""

import asyncio
import uuid
from enum import Enum

import pytest
from pydantic import BaseModel

from eggai import Agent, Channel
from eggai.schemas import BaseMessage
from eggai.transport import KafkaTransport, eggai_set_default_transport


class OrderStatus(Enum):
    """Order processing status enumeration."""

    REQUESTED = "requested"
    CREATED = "created"
    PROCESSED = "processed"
    PENDING = "pending"
    COMPLETED = "completed"


class Order(BaseModel):
    """Order data model with typed fields."""

    order_id: int
    user_id: str
    amount: float
    status: OrderStatus


class Payment(BaseModel):
    """Payment data model with typed fields."""

    payment_id: str
    order_id: int
    status: OrderStatus


class OrderMessage(BaseMessage[Order]):
    """Typed message wrapper for Order data."""

    type: str = "OrderMessage"


class PaymentMessage(BaseMessage[Payment]):
    """Typed message wrapper for Payment data."""

    type: str = "PaymentMessage"


@pytest.mark.asyncio
async def test_basic_typed_subscribe():
    """Test basic typed subscription functionality"""
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create test-specific agent and channel
    agent = Agent("BasicTypedSubscribeAgent")
    channel = Channel(f"test-basic-{uuid.uuid4().hex[:8]}")

    hits = {}
    captured_messages = []

    def hit(key):
        hits[key] = hits.get(key, 0) + 1

    def capture_message(message):
        captured_messages.append(message)

    @agent.subscribe(data_type=OrderMessage, channel=channel)
    async def handle_any_order_message(order: OrderMessage):
        hit("any_order")
        capture_message(order.data)

    @agent.subscribe(
        data_type=OrderMessage,
        channel=channel,
        filter_by_data=lambda order: order.data.status == OrderStatus.REQUESTED,
    )
    async def handle_order_requested(order: OrderMessage):
        hit("order_requested")
        capture_message(order)
        await channel.publish(
            OrderMessage(
                source="test-agent",
                data=Order(
                    order_id=order.data.order_id,
                    user_id=order.data.user_id,
                    amount=order.data.amount,
                    status=OrderStatus.CREATED,
                ),
            )
        )

    @agent.subscribe(
        data_type=OrderMessage,
        channel=channel,
        filter_by_data=lambda order: order.data.status == OrderStatus.CREATED,
    )
    async def handle_order_created(order: OrderMessage):
        hit("order_created")
        capture_message(order.data)

    await agent.start()

    # Publish an order message using BaseMessage format
    await channel.publish(
        OrderMessage(
            source="test-service",
            data=Order(
                order_id=123,
                user_id="user456",
                amount=99.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    await asyncio.sleep(0.5)

    # Should hit handlers correctly:
    # - any_order: 2 times (original + follow-up message)
    # - order_requested: 1 time (only original message with status=requested)
    # - order_created: 1 time (only follow-up message with status=created)
    assert hits.get("any_order") == 2
    assert hits.get("order_requested") == 1
    assert hits.get("order_created") == 1

    # Check that messages were properly typed
    order_messages = [msg for msg in captured_messages if isinstance(msg, Order)]
    assert len(order_messages) >= 2

    # Verify the first message (order_requested)
    first_msg = order_messages[0]
    assert first_msg.status == OrderStatus.REQUESTED
    assert first_msg.order_id == 123
    assert first_msg.user_id == "user456"
    assert first_msg.amount == 99.99

    await agent.stop()


@pytest.mark.asyncio
async def test_typed_subscribe_with_filter():
    """Test typed subscription with filter_by_data using typed fields"""
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create test-specific agent and channel
    agent = Agent("FilterTypedSubscribeAgent")
    channel = Channel(f"test-filter-{uuid.uuid4().hex[:8]}")

    hits = {}
    captured_messages = []

    def hit(key):
        hits[key] = hits.get(key, 0) + 1

    def capture_message(message):
        captured_messages.append(message)

    @agent.subscribe(
        data_type=OrderMessage,
        channel=channel,
        filter_by_data=lambda order: order.data.status == OrderStatus.REQUESTED,
    )
    async def handle_order_requested(order: OrderMessage):
        hit("order_requested")
        capture_message(order.data)

    @agent.subscribe(data_type=PaymentMessage, channel=channel)
    async def handle_payment_message(payment: PaymentMessage):
        hit("payment")
        capture_message(payment.data)

    await agent.start()

    # Publish different types of messages using BaseMessage format
    await channel.publish(
        OrderMessage(
            source="test-service",
            data=Order(
                order_id=456,
                user_id="user789",
                amount=149.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    await channel.publish(
        PaymentMessage(
            source="payment-service",
            data=Payment(
                payment_id="pay_123", order_id=456, status=OrderStatus.COMPLETED
            ),
        )
    )

    await asyncio.sleep(0.5)

    # order_requested should trigger filtered handler
    assert hits.get("order_requested") == 1
    # payment should be handled by payment handler
    assert hits.get("payment") == 1

    # Verify typed access in filter worked
    payment_messages = [msg for msg in captured_messages if isinstance(msg, Payment)]
    assert len(payment_messages) == 1
    assert payment_messages[0].payment_id == "pay_123"
    assert payment_messages[0].status == OrderStatus.COMPLETED

    await agent.stop()


@pytest.mark.asyncio
async def test_typed_subscribe_error_handling():
    """Test error handling when message doesn't match schema"""
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create test-specific agent and channel
    error_agent = Agent("ErrorTestAgent")
    channel = Channel(f"test-error-{uuid.uuid4().hex[:8]}")

    error_hits = {}

    def error_hit(key):
        error_hits[key] = error_hits.get(key, 0) + 1

    @error_agent.subscribe(data_type=OrderMessage, channel=channel)
    async def handle_with_error(order: OrderMessage):
        error_hit("should_not_be_called")

    await error_agent.start()

    # Test 1: Wrong message type (should be ignored, not cause error)
    class WrongMessage(BaseMessage[Order]):
        type: str = "WrongMessage"

    await channel.publish(
        WrongMessage(
            source="test-service",
            data=Order(
                order_id=123,
                user_id="user456",
                amount=99.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    # Test 2: Correct type but invalid payload data - create a dict directly
    await channel.publish(
        {
            "type": "OrderMessage",
            "source": "test-service",
            "data": {
                # Missing required fields: order_id, user_id, amount, status
                "invalid_field": "value"
            },
        }
    )

    await asyncio.sleep(0.5)

    # Handler should not be called in either case
    assert error_hits.get("should_not_be_called") is None

    await error_agent.stop()


@pytest.mark.asyncio
async def test_multiple_typed_subscriptions():
    """Test multiple typed subscriptions on the same agent"""
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create test-specific agent and channel
    multi_agent = Agent("MultiTypedAgent")
    channel = Channel(f"test-multi-{uuid.uuid4().hex[:8]}")

    multi_hits = {}
    multi_messages = []

    def multi_hit(key):
        multi_hits[key] = multi_hits.get(key, 0) + 1

    @multi_agent.subscribe(data_type=OrderMessage, channel=channel)
    async def handle_order(order: OrderMessage):
        multi_hit("order")
        multi_messages.append(order.data)

    @multi_agent.subscribe(data_type=PaymentMessage, channel=channel)
    async def handle_payment(payment: PaymentMessage):
        multi_hit("payment")
        multi_messages.append(payment.data)

    await multi_agent.start()

    # Publish both types using BaseMessage format
    await channel.publish(
        OrderMessage(
            source="test-service",
            data=Order(
                order_id=789,
                user_id="user999",
                amount=199.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    await channel.publish(
        PaymentMessage(
            source="payment-service",
            data=Payment(
                payment_id="pay_456", order_id=789, status=OrderStatus.PENDING
            ),
        )
    )

    await asyncio.sleep(0.5)

    assert multi_hits.get("order") == 1
    assert multi_hits.get("payment") == 1
    assert len(multi_messages) == 2

    # Verify correct typing
    order_msg = next(msg for msg in multi_messages if isinstance(msg, Order))
    payment_msg = next(msg for msg in multi_messages if isinstance(msg, Payment))

    assert order_msg.order_id == 789
    assert payment_msg.payment_id == "pay_456"

    await multi_agent.stop()


@pytest.mark.asyncio
async def test_type_name_matching():
    """Test that message type must match payload class name + 'Message'"""
    eggai_set_default_transport(lambda: KafkaTransport())

    # Create test-specific agent and channel
    type_agent = Agent("TypeMatchingAgent")
    channel = Channel(f"test-type-{uuid.uuid4().hex[:8]}")

    type_hits = {}

    def type_hit(key):
        type_hits[key] = type_hits.get(key, 0) + 1

    @type_agent.subscribe(data_type=OrderMessage, channel=channel)
    async def handle_order(order: OrderMessage):
        type_hit("order_handled")

    await type_agent.start()

    # Should work: OrderMessage matches Order + "Message"
    await channel.publish(
        OrderMessage(
            source="test-service",
            data=Order(
                order_id=123,
                user_id="user456",
                amount=99.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    # Should NOT work: Different type name
    class DifferentMessage(BaseMessage[Order]):
        type: str = "DifferentMessage"

    await channel.publish(
        DifferentMessage(
            source="test-service",
            data=Order(
                order_id=456,
                user_id="user789",
                amount=149.99,
                status=OrderStatus.REQUESTED,
            ),
        )
    )

    await asyncio.sleep(0.5)

    # Only the first message should be handled
    assert type_hits.get("order_handled") == 1

    await type_agent.stop()
