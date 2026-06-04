"""
Shared message-filtering utilities for transport implementations.

Kafka and Redis both apply EggAI's content filtering (``filter_by_message``) and
typed-subscription support (``data_type`` / ``filter_by_data``) by wrapping the
handler, *not* via broker subscriber middlewares. FastStream 0.7 removed the
``middlewares`` argument from ``subscriber()`` (and from the broker constructor),
so the old middleware-based approach raised ``TypeError`` at subscribe time. This
handler-wrapping approach is independent of FastStream's middleware API and keeps
the behaviour identical across the Kafka, Redis, and in-memory transports.
"""

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

# Identity attributes copied from the user handler onto a wrapper. We intentionally
# do NOT use functools.wraps here: it sets __wrapped__, which inspect.signature
# follows — FastStream would then introspect the *original* handler's signature
# (e.g. ``order: OrderMessage``) and try to decode the message into that type
# itself, before our wrapper runs. Our wrappers must keep their own ``(message)``
# signature so FastStream hands them the raw dict to validate/filter. Copying just
# these attributes preserves the handler's name/docs for logging and AsyncAPI
# without changing what FastStream decodes.
_IDENTITY_ATTRS = ("__module__", "__name__", "__qualname__", "__doc__")


def _carry_identity(wrapper: Callable, handler: Callable) -> Callable:
    for attr in _IDENTITY_ATTRS:
        try:
            setattr(wrapper, attr, getattr(handler, attr))
        except AttributeError:
            pass
    return wrapper


async def _invoke(handler: Callable, arg: Any) -> Any:
    """Call ``handler`` with ``arg``, awaiting the result only if it is awaitable.

    Mirrors ``make_tracing_wrapper``'s tolerance of synchronous handlers: a sync
    handler combined with a filter option must not raise ``TypeError`` from an
    unconditional ``await``.
    """
    result = handler(arg)
    if inspect.isawaitable(result):
        return await result
    return result


def wrap_handler_with_filters(
    handler: Callable,
    *,
    data_type: type | None = None,
    filter_by_data: Callable[[Any], bool] | None = None,
    filter_by_message: Callable[[dict[str, Any]], bool] | None = None,
) -> Callable:
    """Wrap ``handler`` with EggAI's content filtering / typed-message support.

    The returned coroutine receives the broker-decoded message (a ``dict``) and:

    - ``data_type``: validates the dict against the Pydantic model. Messages that
      fail validation, or whose ``type`` field does not match the model's default
      ``type``, are skipped. Matching messages are passed to ``handler`` as the
      **typed model instance** (e.g. ``OrderMessage``), not the raw dict.
    - ``data_type`` + ``filter_by_data``: as above, and additionally skipped unless
      ``filter_by_data(typed_message)`` returns truthy.
    - ``filter_by_message`` (no ``data_type``): ``handler`` is called with the raw
      dict only when ``filter_by_message(dict)`` returns truthy.

    Skipped messages return ``None`` without invoking ``handler`` — a clean no-op,
    so the broker acknowledges them (they are not retried). When no filtering
    option is supplied, ``handler`` is returned unchanged.

    ``filter_by_message`` and ``data_type`` are mutually exclusive: the former is
    the untyped (raw-dict) filter, the latter validates into a typed model and
    pairs with ``filter_by_data``. ``filter_by_data`` requires ``data_type``.
    Invalid combinations raise ``ValueError`` rather than silently dropping an
    option.
    """
    if data_type is not None and filter_by_message is not None:
        raise ValueError(
            "filter_by_message cannot be combined with data_type. Use filter_by_data "
            "(which receives the validated typed message) to filter typed "
            "subscriptions, or filter_by_message on its own for raw-dict filtering."
        )
    if filter_by_data is not None and data_type is None:
        raise ValueError(
            "filter_by_data requires data_type — it receives the validated typed "
            "message. Use filter_by_message to filter on the raw dict instead."
        )

    if data_type is not None:
        if "type" not in data_type.model_fields:
            raise ValueError(
                f"data_type {data_type.__name__!r} must define a 'type' field "
                "(the discriminator used to match messages, as on BaseMessage)."
            )
        expected_type = data_type.model_fields["type"].default

        async def typed_handler(message: dict[str, Any]) -> Any:
            try:
                typed_message = data_type.model_validate(message)
            except (ValidationError, ValueError, TypeError):
                # Wrong shape / payload for this data_type — not ours to handle.
                return None
            if typed_message.type != expected_type:
                return None
            if filter_by_data is not None and not filter_by_data(typed_message):
                return None
            return await _invoke(handler, typed_message)

        return _carry_identity(typed_handler, handler)

    if filter_by_message is not None:

        async def filtered_handler(message: dict[str, Any]) -> Any:
            if filter_by_message(message):
                return await _invoke(handler, message)
            return None

        return _carry_identity(filtered_handler, handler)

    return handler
