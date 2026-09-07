"""Contract tests for the CloudEvents envelope models."""

import pytest
from pydantic import BaseModel, ValidationError

from eggai.schemas import BaseMessage, Message


class Order(BaseModel):
    order_id: int


class OrderMessage(BaseMessage[Order]):
    type: str = "OrderMessage"


def test_typed_subclass_requires_data():
    # Without this, a missing payload silently became `data == {}` (pydantic
    # does not validate defaults) and every attribute access crashed downstream.
    with pytest.raises(ValidationError):
        OrderMessage.model_validate({"source": "t", "type": "OrderMessage"})


def test_typed_subclass_validates_data_shape():
    with pytest.raises(ValidationError):
        OrderMessage.model_validate(
            {"source": "t", "type": "OrderMessage", "data": {"unexpected": 1}}
        )


def test_typed_subclass_accepts_valid_data():
    msg = OrderMessage.model_validate(
        {"source": "t", "type": "OrderMessage", "data": {"order_id": 7}}
    )
    assert isinstance(msg.data, Order)
    assert msg.data.order_id == 7


def test_untyped_base_message_defaults_to_empty_dict():
    # Only typed subclasses reject a missing payload; the generic base keeps
    # working without one (0.4.0 briefly required it, restored in 0.4.1).
    msg = BaseMessage(source="t", type="test.event")
    assert msg.data == {}
    assert BaseMessage.model_validate({"source": "t", "type": "test.event"}).data == {}


def test_message_still_defaults_to_empty_dict():
    # The dict default lives on the concrete Message, where it is honest.
    msg = Message(source="t", type="test.event")
    assert msg.data == {}


def test_message_roundtrips_without_data_key():
    msg = Message.model_validate({"source": "t", "type": "test.event"})
    assert msg.data == {}
