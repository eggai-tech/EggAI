"""The lease options and errors of a Redis Streams subscription.

The part of :mod:`eggai.transport.lease` that needs no Redis client:
``Agent.subscribe`` validates the options at decoration time, and the errors are
exported by :mod:`eggai.transport`, with or without the ``redis`` extra. The
renewal itself is in :mod:`eggai.transport.lease`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# The subscribe options of a lease (popped by RedisTransport.subscribe).
LEASE_OPTION_KEYS = (
    "renew_lease",
    "renew_lease_interval_ms",
    "cancel_on_lease_lost",
    "max_processing_ms",
)


class LeaseLostError(Exception):
    """A handler's stream entry left its consumer's PEL while it was running.

    Raised by a ``renew_lease`` subscription (with the default
    ``cancel_on_lease_lost=True``) in place of the handler's result, after the
    handler was cancelled. The entry was reclaimed (usually after renewals kept
    failing for longer than ``retry_on_idle_ms``, e.g. during a Redis outage)
    and has been, or will be, redelivered; cancelling this run keeps it from
    running in parallel with that redelivery. Also raised, without running the
    handler, for an entry that was lost while it was still queued in the
    process. The entry is not acked: it is not this consumer's any more.

    A batch is one unit: if any of its entries is lost, the batch handler is
    cancelled and none is acked; the entries still owned stay pending and are
    retried. ``message_ids`` are all the run's entries, ``lost_ids`` the ones
    that left the PEL.
    """

    def __init__(
        self,
        stream: str,
        group: str,
        message_ids: Iterable[str],
        lost_ids: Iterable[str] | None = None,
    ):
        self.stream = stream
        self.group = group
        self.message_ids = tuple(message_ids)
        self.lost_ids = tuple(lost_ids) if lost_ids is not None else self.message_ids
        super().__init__(
            f"lease lost on stream {stream!r} group {group!r} for "
            f"{', '.join(self.lost_ids)}: the entry left this consumer's PEL "
            "(reclaimed for redelivery); the handler was cancelled"
            + (
                f" (batch of {', '.join(self.message_ids)})"
                if self.lost_ids != self.message_ids
                else ""
            )
        )


class ProcessingTimeoutError(TimeoutError):
    """A handler ran longer than its subscription's ``max_processing_ms``.

    The handler was cancelled and the entry is NACKed (left in the PEL), so the
    reclaimer retries it after ``retry_on_idle_ms``, counting towards
    ``max_retries`` like any other failure.
    """

    def __init__(
        self,
        stream: str,
        group: str,
        message_ids: Iterable[str],
        max_processing_ms: int,
    ):
        self.stream = stream
        self.group = group
        self.message_ids = tuple(message_ids)
        self.max_processing_ms = max_processing_ms
        super().__init__(
            f"handler exceeded max_processing_ms={max_processing_ms} on stream "
            f"{stream!r} group {group!r} for {', '.join(self.message_ids)}; "
            "cancelled, the entry is left for retry"
        )


@dataclass(frozen=True)
class LeaseOptions:
    """Validated lease-related subscribe options."""

    renew_lease: bool = False
    interval_ms: int | None = None  # resolved: retry_on_idle_ms // 3 by default
    cancel_on_lease_lost: bool = True
    max_processing_ms: int | None = None


def _is_positive_int(value: Any) -> bool:
    # bool is an int subclass: True must not pass as 1 ms.
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def resolve_lease_options(
    options: Mapping[str, Any],
    retry_on_idle_ms: int | None,
    *,
    no_ack: bool = False,
) -> LeaseOptions:
    """Validate the lease options in ``options`` (a subscribe kwargs mapping).

    Shared by ``Agent.subscribe`` (decoration time) and
    ``RedisTransport.subscribe``, so a bad combination fails the same way on
    both paths. ``retry_on_idle_ms`` is the subscription's reclaim threshold and
    ``no_ack`` its ``no_ack`` option. ``options`` is only read, never modified.
    """
    lease = options.get("renew_lease", False)
    interval_ms = options.get("renew_lease_interval_ms")
    cancel_on_lost = options.get("cancel_on_lease_lost", True)
    max_processing_ms = options.get("max_processing_ms")
    if not isinstance(lease, bool):
        raise ValueError("renew_lease must be True or False")
    if not isinstance(cancel_on_lost, bool):
        raise ValueError("cancel_on_lease_lost must be True or False")
    if not lease:
        if interval_ms is not None or "cancel_on_lease_lost" in options:
            raise ValueError(
                "renew_lease_interval_ms / cancel_on_lease_lost require "
                "renew_lease=True."
            )
    else:
        if retry_on_idle_ms is None:
            raise ValueError(
                "renew_lease requires retry_on_idle_ms: the lease keeps the "
                "SDK-managed reclaimer from redelivering an entry that is still "
                "being processed, and without retry_on_idle_ms there is none."
            )
        if interval_ms is None:
            interval_ms = max(1, retry_on_idle_ms // 3)
            if interval_ms >= retry_on_idle_ms:
                # Only for retry_on_idle_ms < 2: no renewal interval fits.
                raise ValueError(
                    "renew_lease requires retry_on_idle_ms >= 2: leases are "
                    "renewed every renew_lease_interval_ms (a positive int "
                    "< retry_on_idle_ms)."
                )
        elif not _is_positive_int(interval_ms):
            raise ValueError("renew_lease_interval_ms must be a positive int")
        elif interval_ms >= retry_on_idle_ms:
            raise ValueError(
                "renew_lease_interval_ms must be < retry_on_idle_ms: an entry "
                "renewed less often than the reclaim threshold is reclaimed "
                "between two renewals (the default is retry_on_idle_ms // 3)."
            )
        if no_ack:
            raise ValueError(
                "renew_lease is incompatible with no_ack=True: with no ack "
                "there is no PEL entry to renew."
            )
    if max_processing_ms is not None:
        if not _is_positive_int(max_processing_ms):
            raise ValueError("max_processing_ms must be a positive int")
        if retry_on_idle_ms is None:
            raise ValueError(
                "max_processing_ms requires retry_on_idle_ms: a handler past its "
                "deadline is NACKed, and only the SDK-managed reclaimer retries a "
                "NACKed entry."
            )
        if no_ack:
            raise ValueError(
                "max_processing_ms is incompatible with no_ack=True: a handler "
                "past its deadline is left in the PEL for retry, and with no ack "
                "there is no PEL entry, so the message would be lost."
            )
    return LeaseOptions(
        renew_lease=lease,
        interval_ms=interval_ms if lease else None,
        cancel_on_lease_lost=cancel_on_lost,
        max_processing_ms=max_processing_ms,
    )
