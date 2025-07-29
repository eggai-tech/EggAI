import asyncio
import uuid
from enum import Enum

import pytest
from pydantic import BaseModel

from eggai import Agent, Channel
from eggai.schemas import BaseMessage
from eggai.transport import eggai_set_default_transport, KafkaTransport


class Status(Enum):
    REQUESTED = "requested"
    CREATED = "created"
    PROCESSED = "processed"
    PENDING = "pending"
    COMPLETED = "completed"


# Payload classes (without Message suffix)
class Order(BaseModel):
    order_id: int
    user_id: str
    amount: float
    status: Status


class Payment(BaseModel):
    payment_id: str
    order_id: int
    status: Status


# Message classes using BaseMessage
class OrderMessage(BaseMessage[Order]):
    type: str = "OrderMessage"


class PaymentMessage(BaseMessage[Payment]):
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

    @agent.typed_subscribe(Order, channel=channel)
    async def handle_any_order_message(order: Order):
        hit("any_order")
        capture_message(order)

    @agent.typed_subscribe(
        Order, 
        channel=channel,
        filter_by_message=lambda order: order.status == Status.REQUESTED
    )
    async def handle_order_requested(order: Order):
        hit("order_requested")
        capture_message(order)
        # Publish a follow-up message
        await channel.publish(OrderMessage(
            source="test-agent",
            data=Order(
                order_id=order.order_id,
                user_id=order.user_id,
                amount=order.amount,
                status=Status.CREATED
            )
        ))

    @agent.typed_subscribe(
        Order,
        channel=channel,
        filter_by_message=lambda order: order.status == Status.CREATED
    )
    async def handle_order_created(order: Order):
        hit("order_created")
        capture_message(order)
    
    await agent.start()
    
    # Publish an order message using BaseMessage format
    await channel.publish(OrderMessage(
        source="test-service",
        data=Order(
            order_id=123,
            user_id="user456",
            amount=99.99,
            status=Status.REQUESTED
        )
    ))
    
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
    assert first_msg.status == Status.REQUESTED
    assert first_msg.order_id == 123
    assert first_msg.user_id == "user456"
    assert first_msg.amount == 99.99
    
    await agent.stop()


@pytest.mark.asyncio
async def test_typed_subscribe_with_filter():
    """Test typed subscription with filter_by_message using typed fields"""
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

    @agent.typed_subscribe(
        Order, 
        channel=channel,
        filter_by_message=lambda order: order.status == Status.REQUESTED
    )
    async def handle_order_requested(order: Order):
        hit("order_requested")
        capture_message(order)

    @agent.typed_subscribe(Payment, channel=channel)
    async def handle_payment_message(payment: Payment):
        hit("payment")
        capture_message(payment)
    
    await agent.start()
    
    # Publish different types of messages using BaseMessage format
    await channel.publish(OrderMessage(
        source="test-service",
        data=Order(
            order_id=456,
            user_id="user789",
            amount=149.99,
            status=Status.REQUESTED
        )
    ))
    
    await channel.publish(PaymentMessage(
        source="payment-service",
        data=Payment(
            payment_id="pay_123",
            order_id=456,
            status=Status.COMPLETED
        )
    ))
    
    await asyncio.sleep(0.5)
    
    # order_requested should trigger filtered handler
    assert hits.get("order_requested") == 1
    # payment should be handled by payment handler
    assert hits.get("payment") == 1
    
    # Verify typed access in filter worked
    payment_messages = [msg for msg in captured_messages if isinstance(msg, Payment)]
    assert len(payment_messages) == 1
    assert payment_messages[0].payment_id == "pay_123"
    assert payment_messages[0].status == Status.COMPLETED
    
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
    
    @error_agent.typed_subscribe(Order, channel=channel)
    async def handle_with_error(order: Order):
        error_hit("should_not_be_called")
    
    await error_agent.start()
    
    # Test 1: Wrong message type (should be ignored, not cause error)
    class WrongMessage(BaseMessage[Order]):
        type: str = "WrongMessage"
    
    await channel.publish(WrongMessage(
        source="test-service",
        data=Order(
            order_id=123,
            user_id="user456", 
            amount=99.99,
            status=Status.REQUESTED
        )
    ))
    
    # Test 2: Correct type but invalid payload data - create a dict directly
    await channel.publish({
        "type": "OrderMessage",
        "source": "test-service",
        "data": {
            # Missing required fields: order_id, user_id, amount, status
            "invalid_field": "value"
        }
    })
    
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
    
    @multi_agent.typed_subscribe(Order, channel=channel)
    async def handle_order(order: Order):
        multi_hit("order")
        multi_messages.append(order)
    
    @multi_agent.typed_subscribe(Payment, channel=channel)
    async def handle_payment(payment: Payment):
        multi_hit("payment")
        multi_messages.append(payment)
    
    await multi_agent.start()
    
    # Publish both types using BaseMessage format
    await channel.publish(OrderMessage(
        source="test-service",
        data=Order(
            order_id=789,
            user_id="user999",
            amount=199.99,
            status=Status.REQUESTED
        )
    ))
    
    await channel.publish(PaymentMessage(
        source="payment-service",
        data=Payment(
            payment_id="pay_456",
            order_id=789,
            status=Status.PENDING
        )
    ))
    
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
    
    @type_agent.typed_subscribe(Order, channel=channel)
    async def handle_order(order: Order):
        type_hit("order_handled")
    
    await type_agent.start()
    
    # Should work: OrderMessage matches Order + "Message"
    await channel.publish(OrderMessage(
        source="test-service",
        data=Order(
            order_id=123,
            user_id="user456",
            amount=99.99,
            status=Status.REQUESTED
        )
    ))
    
    # Should NOT work: Different type name
    class DifferentMessage(BaseMessage[Order]):
        type: str = "DifferentMessage"
    
    await channel.publish(DifferentMessage(
        source="test-service",
        data=Order(
            order_id=456,
            user_id="user789",
            amount=149.99,
            status=Status.REQUESTED
        )
    ))
    
    await asyncio.sleep(0.5)
    
    # Only the first message should be handled
    assert type_hits.get("order_handled") == 1
    
    await type_agent.stop()