"""Unit tests for the shared handler-filtering wrapper.

These are intentionally broker-independent so they run in CI even when no Redis or
Kafka service is available (the integration suites are auto-skipped without one).
They lock in the contract that both the Redis and Kafka transports rely on after
FastStream 0.7 removed subscriber middlewares.
"""

import pytest
from pydantic import BaseModel

from eggai.schemas import BaseMessage
from eggai.transport.middleware_utils import wrap_handler_with_filters


class Order(BaseModel):
    order_id: int
    status: str


class OrderMessage(BaseMessage[Order]):
    type: str = "OrderMessage"


def _order_msg(order_id=1, status="new", **overrides):
    payload = OrderMessage(source="t", data=Order(order_id=order_id, status=status))
    # Brokers hand the handler a decoded dict, so feed the wrapper a dict.
    return {**payload.model_dump(mode="json"), **overrides}


@pytest.mark.asyncio
async def test_no_options_returns_handler_unchanged():
    async def handler(m):
        return m

    assert wrap_handler_with_filters(handler) is handler


@pytest.mark.asyncio
async def test_filter_by_message_passes_dict_on_match():
    seen = []

    async def handler(m):
        seen.append(m)

    wrapped = wrap_handler_with_filters(
        handler, filter_by_message=lambda m: m["type"] == "keep"
    )
    await wrapped({"type": "keep", "v": 1})
    await wrapped({"type": "drop", "v": 2})

    assert seen == [{"type": "keep", "v": 1}]


@pytest.mark.asyncio
async def test_data_type_delivers_typed_instance():
    seen = []

    async def handler(order):
        seen.append(order)

    wrapped = wrap_handler_with_filters(handler, data_type=OrderMessage)
    await wrapped(_order_msg(order_id=42, status="new"))

    assert len(seen) == 1
    assert isinstance(seen[0], OrderMessage)  # typed, not dict
    assert seen[0].data.order_id == 42


@pytest.mark.asyncio
async def test_data_type_skips_wrong_type():
    seen = []

    async def handler(order):
        seen.append(order)

    wrapped = wrap_handler_with_filters(handler, data_type=OrderMessage)
    # Right shape, wrong discriminator.
    await wrapped(_order_msg(type="SomethingElse"))

    assert seen == []


@pytest.mark.asyncio
async def test_data_type_skips_invalid_payload():
    seen = []

    async def handler(order):
        seen.append(order)

    wrapped = wrap_handler_with_filters(handler, data_type=OrderMessage)
    # Correct discriminator, invalid payload → ValidationError → skipped, no raise.
    await wrapped({"type": "OrderMessage", "source": "t", "data": {"bad": True}})

    assert seen == []


def test_data_type_with_filter_by_message_is_rejected():
    """Combining data_type with filter_by_message is a footgun (one would be
    silently dropped), so it must raise rather than quietly ignore the predicate."""

    async def handler(m):
        return m

    with pytest.raises(ValueError, match="cannot be combined with data_type"):
        wrap_handler_with_filters(
            handler,
            data_type=OrderMessage,
            filter_by_message=lambda m: True,
        )


@pytest.mark.asyncio
async def test_filter_by_data_narrows_typed_messages():
    seen = []

    async def handler(order):
        seen.append(order.data.order_id)

    wrapped = wrap_handler_with_filters(
        handler,
        data_type=OrderMessage,
        filter_by_data=lambda o: o.data.status == "shipped",
    )
    await wrapped(_order_msg(order_id=1, status="new"))
    await wrapped(_order_msg(order_id=2, status="shipped"))

    assert seen == [2]
