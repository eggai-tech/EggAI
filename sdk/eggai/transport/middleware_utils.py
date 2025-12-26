"""
Shared middleware utilities for transport implementations.

This module provides common middleware factories used by Kafka and Redis transports
to handle message filtering and data type validation.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from faststream.message.message import StreamMessage


def create_filter_middleware(filter_func: Callable[[dict[str, Any]], bool]) -> Callable:
    """
    Create a middleware that filters messages based on a predicate function.

    Args:
        filter_func: A function that takes a message dict and returns True if the message
                    should be processed, False otherwise.

    Returns:
        A middleware function that applies the filter.
    """

    async def middleware(
        call_next: Callable[[Any], Awaitable[Any]],
        msg: StreamMessage[Any],
    ) -> Any:
        if filter_func(json.loads(msg.body.decode("utf-8"))):
            return await call_next(msg)
        return None

    return middleware


def create_data_type_middleware(data_type: type) -> Callable:
    """
    Create a middleware that validates and filters messages by data type.

    Args:
        data_type: A Pydantic model class with a 'type' field that will be used
                  for validation and filtering.

    Returns:
        A middleware function that validates the message against the data type
        and filters out messages that don't match the expected type.
    """

    async def middleware(
        call_next: Callable[[Any], Awaitable[Any]],
        msg: StreamMessage[Any],
    ) -> Any:
        typed_message = data_type.model_validate(json.loads(msg.body.decode("utf-8")))

        if typed_message.type != data_type.model_fields["type"].default:
            return None

        return await call_next(msg)

    return middleware


def create_filter_by_data_middleware(
    data_type: type, filter_func: Callable[[Any], bool]
) -> Callable:
    """
    Create a middleware that validates messages by data type and applies a filter.

    This combines data type validation with a custom filter function that operates
    on the validated/typed message object.

    Args:
        data_type: A Pydantic model class for validation.
        filter_func: A function that takes the validated message object and returns
                    True if it should be processed, False otherwise.

    Returns:
        A middleware function that validates and filters messages.
    """

    async def middleware(
        call_next: Callable[[Any], Awaitable[Any]],
        msg: StreamMessage[Any],
    ) -> Any:
        data = json.loads(msg.body.decode("utf-8"))
        typed_message = data_type.model_validate(data)
        if filter_func(typed_message):
            return await call_next(msg)
        return None

    return middleware
