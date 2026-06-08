import asyncio
import logging
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from faststream import AckPolicy
from faststream.redis import RedisBroker, StreamSub
from redis.exceptions import ResponseError

from eggai.schemas import BaseMessage
from eggai.transport.base import Transport
from eggai.transport.middleware_utils import wrap_handler_with_filters
from eggai.transport.pending_reclaimer import PendingReclaimerManager, ReclaimerConfig

logger = logging.getLogger(__name__)

# Stable for the lifetime of this process, unique across processes/hosts. Used as
# the default Redis stream consumer name so that multiple workers sharing a
# consumer group (same handler code → same group) each claim a distinct slice of
# the stream and own their own PEL entries — the competing-consumers pattern.
_CONSUMER_INSTANCE = f"{socket.gethostname()}-{os.getpid()}"


@dataclass(frozen=True)
class _StreamGroupInfo:
    """Tracks a registered stream consumer group for health monitoring."""

    stream_key: str
    group: str
    group_create_id: str


class RedisTransport(Transport):
    """
    Redis-based transport layer adapted to use FastStream's RedisBroker for message publishing and consumption.

    This class serves as a transport mechanism that integrates with Redis to allow message publishing
    and consumption. It uses the FastStream RedisBroker to interact with Redis, offering methods to
    connect, disconnect, publish messages to Redis channels, and subscribe to Redis channels/streams.

    Attributes:
        broker (RedisBroker): The RedisBroker instance responsible for managing Redis connections and messaging.
    """

    def __init__(
        self,
        broker: RedisBroker | None = None,
        url: str = "redis://localhost:6379",
        group_monitor_interval_s: float = 5.0,
        max_len: int | None = None,
        retry_max_len: int | None = 10_000,
        **kwargs,
    ):
        """
        Initializes the RedisTransport with an optional RedisBroker or creates a new one with provided URL.

        Args:
            broker (Optional[RedisBroker]): An existing RedisBroker instance to use. If not provided, a new instance will
                                             be created with the specified URL and additional parameters.
            url (str): The Redis connection URL (default is "redis://localhost:6379").
            group_monitor_interval_s (float): How often the background monitor re-asserts that every
                registered consumer group exists (default 5.0s).
            max_len (Optional[int]): Approximate cap on the length of streams written by ``publish()``
                (the producer path), applied as ``XADD ... MAXLEN ~ max_len``. Default ``None`` (unbounded).
                NOTE: ``MAXLEN`` trims the *oldest* entries by count regardless of whether they have been
                consumed/acked, so a value smaller than ``throughput × consumer-lag`` can silently drop
                un-delivered messages. Left opt-in for that reason — set it deliberately per your retention
                needs (e.g. 100_000) once you understand your traffic.
            retry_max_len (Optional[int]): Approximate cap on the SDK-managed retry and DLQ streams
                (default 10_000). These hold only reclaimed failures, so their volume is bounded by your
                error rate and a default cap prevents a runaway retry loop from growing without bound.
                Set to ``None`` to disable trimming on retry/DLQ streams.
            **kwargs: Additional keyword arguments to pass to the RedisBroker if a new instance is created.

        Attributes:
            url (str): Redis connection URL in the format `redis://[[username]:[password]]@localhost:6379/0`.
                      Supports also `rediss://` for SSL connections and `unix://` for Unix domain socket.

            decoder (Optional[CustomCallable]): Custom decoder for messages (default is `None`).
            parser (Optional[CustomCallable]): Custom parser for messages (default is `None`).
            dependencies (Iterable[Depends]): Dependencies to apply to all broker subscribers (default is `()`).
            middlewares (Sequence[BrokerMiddleware]): Middlewares to apply to all broker publishers/subscribers (default is `()`).
            security (Optional[BaseSecurity]): Security options for broker connection (default is `None`).
            graceful_timeout (Optional[float]): Graceful shutdown timeout (default is 15.0).

            # Redis-specific parameters
            host (str): Redis server hostname (default is "localhost").
            port (int): Redis server port (default is 6379).
            db (int): Redis database number to use (default is 0).
            password (Optional[str]): Password for authentication (default is `None`).
            socket_timeout (Optional[float]): Socket timeout in seconds (default is `None`).
            socket_connect_timeout (Optional[float]): Socket connection timeout in seconds (default is `None`).
            socket_keepalive (Optional[bool]): Enable TCP keepalive (default is `None`).
            socket_keepalive_options (Optional[Mapping[int, Union[int, bytes]]]): TCP keepalive options (default is `None`).
            connection_pool (Optional[ConnectionPool]): Custom connection pool instance (default is `None`).
            unix_socket_path (Optional[str]): Path to Unix socket for connection (default is `None`).
            encoding (str): Encoding to use for strings (default is "utf-8").
            encoding_errors (str): Error handling scheme for encoding errors (default is "strict").
            decode_responses (bool): Whether to decode responses to strings (default is `False`).
            retry_on_timeout (bool): Whether to retry commands on timeout (default is `False`).
            retry_on_error (Optional[list]): List of error classes to retry on (default is `None`).
            ssl (bool): Whether to use SSL connection (default is `False`).
            ssl_keyfile (Optional[str]): Path to SSL private key file (default is `None`).
            ssl_certfile (Optional[str]): Path to SSL certificate file (default is `None`).
            ssl_cert_reqs (str): Whether to verify SSL certificates ("required", "optional", "none", default is "required").
            ssl_ca_certs (Optional[str]): Path to CA certificates file (default is `None`).
            ssl_check_hostname (bool): Whether to check hostname in SSL cert (default is `False`).
            max_connections (Optional[int]): Maximum number of connections in pool (default is `None`).
            single_connection_client (bool): Force single connection mode (default is `False`).
            health_check_interval (int): Interval in seconds between connection health checks (default is 0).
            client_name (Optional[str]): Name for this client connection (default is `None`).
            username (Optional[str]): Username for ACL authentication (default is `None`).
            protocol (int): RESP protocol version (2 or 3, default is 3).

            # AsyncAPI documentation parameters
            asyncapi_url (Union[str, Iterable[str], None]): AsyncAPI server URL (default is `None`).
            protocol_version (Optional[str]): AsyncAPI server protocol version (default is "auto").
            description (Optional[str]): AsyncAPI server description (default is `None`).
            tags (Optional[Iterable[Union["asyncapi.Tag", "asyncapi.TagDict"]]]): AsyncAPI server tags (default is `None`).

            # Logging parameters
            logger (Optional[LoggerProto]): Custom logger to pass into context (default is `EMPTY`).
            log_level (int): Log level for service messages (default is `logging.INFO`).
            log_fmt (Optional[str]): Log format (default is `None`).
        """
        if broker:
            self.broker = broker
        else:
            self.broker = RedisBroker(url, log_level=logging.INFO, **kwargs)
        self._redis_url = url
        self._max_len = max_len
        self._retry_max_len = retry_max_len
        self._running = False
        self._reclaimer_manager: PendingReclaimerManager | None = None
        # A set so repeated subscribe() calls with an identical (stream_key, group,
        # group_create_id) collapse instead of accumulating duplicate XGROUP CREATE
        # work in the monitor. _StreamGroupInfo is frozen/hashable.
        self._stream_subscriptions: set[_StreamGroupInfo] = set()
        self._group_monitor_task: asyncio.Task | None = None
        self._group_monitor_interval_s: float = group_monitor_interval_s

    async def connect(self):
        """
        Establishes a connection to the Redis server by starting the RedisBroker instance.

        This method is necessary before publishing or consuming messages. It asynchronously starts the broker
        to handle Redis communication.
        """
        # broker.start() creates all consumer groups (and streams via MKSTREAM).
        # Both the main and retry subscriptions were registered in subscribe() before
        # connect() is called, so all groups exist after this line.
        #
        # A single RedisTransport may be shared across multiple Agents, and each
        # Agent.start() calls connect(). FastStream's broker.start() restarts
        # *every* registered subscriber on each call (it carries an upstream TODO
        # to guard this), which would spawn a duplicate consume loop for handlers
        # already running from an earlier connect(). Guard against that: do the
        # full start the first time, then on subsequent connect()s only start the
        # subscribers that aren't running yet (e.g. those a second Agent just
        # registered). Falls back to the original full start() if FastStream ever
        # stops exposing the `running` flags.
        if not getattr(self.broker, "running", False):
            await self.broker.start()
        else:
            await self.broker.connect()
            for sub in self.broker.subscribers:
                if not getattr(sub, "running", False):
                    await sub.start()
        if self._reclaimer_manager is not None:
            # start() is idempotent — it skips reclaimer tasks already running.
            await self._reclaimer_manager.start()
        self._running = True
        # Don't overwrite (and orphan) a monitor task still running from an
        # earlier connect() on a shared transport — it already iterates the
        # shared _stream_subscriptions set, which now includes the new groups.
        if self._stream_subscriptions and (
            self._group_monitor_task is None or self._group_monitor_task.done()
        ):
            self._group_monitor_task = asyncio.create_task(
                self._monitor_stream_groups(),
                name="stream-group-monitor",
            )

    async def disconnect(self):
        """
        Closes the connection to the Redis server by stopping the RedisBroker instance.

        This method should be called when the transport is no longer needed to stop consuming messages
        and to release any resources held by the RedisBroker.
        """
        self._running = False
        if self._group_monitor_task is not None:
            self._group_monitor_task.cancel()
            try:
                await self._group_monitor_task
            except asyncio.CancelledError:
                pass
            self._group_monitor_task = None
        if self._reclaimer_manager is not None:
            await self._reclaimer_manager.stop()
        await self.broker.stop()

    async def publish(self, channel: str, message: dict[str, Any] | BaseMessage):
        """
        Publishes a message to the specified Redis stream.

        Args:
            channel (str): The name of the Redis stream to which the message will be published.
            message (Union[Dict[str, Any], BaseMessage]): The message to publish, which can either be a dictionary
                                                         or a BaseMessage instance. The message will be serialized
                                                         before being sent.

        """
        # When max_len is configured, cap the stream approximately (XADD MAXLEN ~)
        # so the producer path can't grow without bound. None → no trimming.
        if self._max_len is not None:
            await self.broker.publish(message, stream=channel, maxlen=self._max_len)
        else:
            await self.broker.publish(message, stream=channel)

    async def subscribe(self, channel: str, handler, **kwargs) -> Callable:
        """
        Subscribes to a Redis channel and sets up a handler to process incoming messages.

        Args:
            channel (str): The Redis channel to subscribe to.
            handler (Callable): The function or coroutine that will handle messages received from the channel.
            **kwargs: Additional keyword arguments that can be used to configure the subscription.

        Keyword Args:
            filter_by_message (Callable, optional): Predicate applied to the decoded message dict; the handler
                is invoked (with the dict) only for messages where it returns truthy. Non-matching messages
                are skipped (acked, not retried).
            data_type (BaseModel, optional): A Pydantic model class used to validate and type incoming messages.
                Messages that fail validation, or whose ``type`` field does not match the model's default
                ``type``, are skipped. Matching messages are passed to the handler as the **typed model
                instance** (not the raw dict).
            filter_by_data (Callable, optional): Predicate applied to the validated typed message (requires
                `data_type`); the handler runs only when it returns truthy.

            # Redis Pub/Sub parameters
            pattern (bool, optional): Whether to use pattern-based subscription (default is False).

            # Redis Stream parameters
            stream (Optional[str], optional): Redis stream name to consume from instead of Pub/Sub channel.
            polling_interval (int, optional): Interval in milliseconds for polling streams (default is 100).
            group (Optional[str], optional): Consumer group name for stream consumption. Defaults to the
                handler_id, which is stable across workers running the same handler — so a fleet of workers
                shares one group and load-balances the stream (competing consumers).
            consumer (Optional[str], optional): Consumer name within the group. Defaults to a
                per-process-unique name (``{handler_id}-{hostname}-{pid}``) so each worker in the group owns
                a distinct slice of the PEL. Pass an explicit value only if you need a stable consumer name.
            batch (bool, optional): Whether to consume messages in batches (default is False).
            max_records (Optional[int], optional): Maximum number of records to consume in one batch (default is None).
            last_id (str, optional): Starting message ID for stream consumption (default is ">" for consumer groups).
            no_ack (bool, optional): Whether to skip acknowledgment of stream messages (default is False for durability).
            ack_policy (AckPolicy, optional): Acknowledgment policy for message handling (default is AckPolicy.NACK_ON_ERROR).
                - NACK_ON_ERROR: Messages are NOT acknowledged on handler errors, allowing redelivery (recommended).
                - ACK: Messages are acknowledged regardless of handler success/failure.
                - REJECT_ON_ERROR: Messages are permanently discarded on handler errors.
                - MANUAL: Full manual control over acknowledgment via msg.ack()/msg.nack().
            min_idle_time (int, optional): Minimum idle time in milliseconds before a pending message can be auto-claimed
                via FastStream's built-in XAUTOCLAIM. Mutually exclusive with retry_on_idle_ms.
            retry_on_idle_ms (int, optional): Enables SDK-managed PEL reclaiming. Messages stuck in the PEL longer than
                this threshold are moved to a dedicated ``{channel}.{handler_suffix}.retry`` stream (per-handler, so
                concurrent handlers on the same channel do not see each other's retries) and re-delivered to the same handler.
                Mutually exclusive with min_idle_time. Recommended: 30_000 (30 seconds).
                Delivery is at-least-once — handlers must be idempotent. Injected fields _retry_count and
                _original_message_id can be used for deduplication.
                Binary (non-UTF-8) field values are not supported.
            retry_reclaim_interval_s (float, optional): How often the reclaimer scans for stuck messages (default 15.0s).
                Only used when retry_on_idle_ms is set.
            retry_backoff_multiplier (float, optional): Exponential backoff factor applied between retry attempts
                (default 1.0 = constant cadence, the original behaviour). A failing message is reclaimed once it has
                been idle for ``retry_on_idle_ms * (retry_backoff_multiplier ** retry_count)``. With base 30s and
                multiplier 2.0 the attempts space out as 30s → 60s → 120s → 240s …, so an overloaded downstream gets
                progressively more room to recover instead of being retried on a fixed clock. Must be >= 1.0.
                Requires retry_on_idle_ms.
            retry_backoff_max_ms (int, optional): Upper bound on the escalated idle threshold so it doesn't grow without
                limit (e.g. 900_000 caps backoff at 15 minutes). Default None (uncapped). Must be >= retry_on_idle_ms.
                Requires retry_on_idle_ms.
            retry_backoff_jitter (float, optional): Fraction in [0.0, 1.0] (default 0.0 = none). Adds a random
                0..jitter share *on top of* each computed threshold, so a fleet of workers that all failed during the
                same outage don't come due in lockstep (thundering herd) on recovery. Jitter is applied upward (never
                below ``retry_on_idle_ms``) because that base is a hard floor — the reclaim scan won't touch an entry
                idle for less than it. The spread is only effective once ``jitter * threshold`` is comparable to
                ``retry_reclaim_interval_s`` (the scan cadence quantises smaller jitter away). Requires retry_on_idle_ms.
            max_retries (int, optional): Maximum number of retry attempts before routing to the Dead Letter Queue
                (``{channel}.{handler_suffix}.dlq``). Default is 5 when retry_on_idle_ms is set. With max_retries=5, the handler is
                called up to 6 times total (1 original + 5 retries). Set to None for unlimited retries (no DLQ).
                Requires retry_on_idle_ms.
            on_dlq (Callable, optional): Callback invoked when a message is routed to the DLQ. Can be sync or async.
                Signature: ``on_dlq(fields: dict, msg_id: str, retry_count: int)``. Errors in the callback are
                logged but never prevent the DLQ write. Only used when retry_on_idle_ms and max_retries are set.
            retry_on_error (bool, optional): Whether to retry handler on error (default is True).

            # Durability parameters
            #
            # Stream length is capped at the transport level, not per-subscriber: pass
            # ``max_len`` (producer/publish path) and/or ``retry_max_len`` (retry & DLQ
            # streams, default 10_000) to ``RedisTransport(...)``. See the constructor docstring.

            # General parameters
            dependencies (Sequence[Depends], optional): Custom dependencies for this subscriber.
            parser (Optional[CustomCallable], optional): Custom parser for this subscriber.
            decoder (Optional[CustomCallable], optional): Custom decoder for this subscriber.
            no_reply (bool, optional): Whether to disable message acknowledgment (default is False).

        Returns:
            Callable: A callback function that represents the subscription. When invoked, it will call the handler with
                      incoming messages.
        """
        # Reclaimer options — extracted before StreamSub is built.
        retry_on_idle_ms = kwargs.pop("retry_on_idle_ms", None)
        retry_reclaim_interval_s = kwargs.pop("retry_reclaim_interval_s", 15.0)
        _explicit_max_retries = "max_retries" in kwargs
        max_retries = kwargs.pop("max_retries", 5)
        on_dlq = kwargs.pop("on_dlq", None)
        _explicit_backoff = (
            "retry_backoff_multiplier" in kwargs
            or "retry_backoff_max_ms" in kwargs
            or "retry_backoff_jitter" in kwargs
        )
        retry_backoff_multiplier = kwargs.pop("retry_backoff_multiplier", 1.0)
        retry_backoff_max_ms = kwargs.pop("retry_backoff_max_ms", None)
        retry_backoff_jitter = kwargs.pop("retry_backoff_jitter", 0.0)
        _internal_retry = kwargs.pop("_internal_retry", False)

        # EggAI applies content filtering (filter_by_message) and typed-subscription
        # support (data_type / filter_by_data) by wrapping the handler — see
        # wrap_handler_with_filters — NOT via FastStream subscriber middlewares,
        # which FastStream 0.7 removed from subscriber()/the broker constructor.
        #
        # Wrapper order matters: tracing must stay OUTERMOST so traceparent is read
        # from the raw decoded dict before a data_type subscription validates it
        # into a typed model (the typed model may not carry the traceparent field).
        # So the stack is  tracing( filters( handler ) ).
        #
        # The tracing wrapper also binds the channel name into each span's
        # messaging.destination, so we wrap per-stream: the main subscriber with
        # `channel` here and (in the retry block below) the retry subscriber with the
        # retry stream key — otherwise retry-attempt spans would report the original
        # channel and could not be dashboarded separately. We keep the unwrapped
        # `original_handler` so the retry block can rebuild the same filter+trace
        # stack. The recursive retry subscribe is marked _internal_retry=True and
        # receives an already-wrapped handler, so it must not wrap again.
        filter_opts = {
            "filter_by_message": kwargs.pop("filter_by_message", None),
            "data_type": kwargs.pop("data_type", None),
            "filter_by_data": kwargs.pop("filter_by_data", None),
        }
        original_handler = handler
        if not _internal_retry:
            from eggai.tracing import make_tracing_wrapper

            handler = make_tracing_wrapper(
                channel, wrap_handler_with_filters(handler, **filter_opts)
            )

        handler_id = kwargs.pop("handler_id", None)

        # Ignore Kafka-specific parameter (Redis uses 'group' for streams, not 'group_id')
        kwargs.pop("group_id", None)

        # Extract stream-related parameters.
        # `group` defaults to handler_id so that multiple workers running the same
        # handler code share one consumer group (Redis distributes new messages
        # across the group — competing-consumers load balancing). `consumer` must
        # be distinct *per worker* within that group, otherwise two processes share
        # one consumer name and their PEL entries become indistinguishable. So when
        # the caller doesn't pin a consumer, default it to a per-process-unique name
        # derived from handler_id. Direct callers passing consumer= keep full
        # control; handler_id=None (no group) leaves consumer None as before.
        group = kwargs.pop("group", handler_id)
        consumer = kwargs.pop("consumer", None)
        if consumer is None:
            consumer = (
                f"{handler_id}-{_CONSUMER_INSTANCE}" if handler_id else handler_id
            )
        polling_interval = kwargs.pop("polling_interval", 100)
        batch = kwargs.pop("batch", False)
        max_records = kwargs.pop("max_records", None)
        last_id = kwargs.pop("last_id", ">")
        no_ack = kwargs.pop("no_ack", False)
        min_idle_time = kwargs.pop("min_idle_time", None)

        if min_idle_time is not None and retry_on_idle_ms is not None:
            raise ValueError(
                "min_idle_time and retry_on_idle_ms are mutually exclusive. "
                "Use retry_on_idle_ms for SDK-managed retry streams, or "
                "min_idle_time for FastStream's built-in XAUTOCLAIM."
            )

        if (
            _explicit_max_retries
            and max_retries is not None
            and retry_on_idle_ms is None
        ):
            raise ValueError(
                "max_retries requires retry_on_idle_ms to be set. "
                "Set retry_on_idle_ms to enable SDK-managed retries with a DLQ."
            )

        if max_retries is not None and max_retries < 1:
            raise ValueError("max_retries must be >= 1")

        # Retry-backoff knobs only have meaning for SDK-managed retries, which are
        # gated on retry_on_idle_ms. Reject them up front otherwise so a typo can't
        # silently no-op (mirrors the max_retries guard above).
        if _explicit_backoff and retry_on_idle_ms is None:
            raise ValueError(
                "retry_backoff_multiplier / retry_backoff_max_ms / "
                "retry_backoff_jitter require retry_on_idle_ms to be set."
            )
        if retry_backoff_multiplier < 1.0:
            raise ValueError(
                "retry_backoff_multiplier must be >= 1.0 (1.0 = constant cadence; "
                "values <1 would retry faster the more a message fails)."
            )
        if not 0.0 <= retry_backoff_jitter <= 1.0:
            raise ValueError("retry_backoff_jitter must be between 0.0 and 1.0")
        if (
            retry_on_idle_ms is not None
            and retry_backoff_max_ms is not None
            and retry_backoff_max_ms < retry_on_idle_ms
        ):
            raise ValueError(
                "retry_backoff_max_ms must be >= retry_on_idle_ms (the base idle "
                "threshold); a cap below the base would disable backoff entirely."
            )

        # SDK-managed retries need failed messages to stay in the PEL so the
        # reclaimer can find them. ACK / ACK_FIRST acknowledge a message even when
        # the handler raises, which empties the PEL and makes retries and the DLQ
        # silently never fire. Reject that combination up front.
        if retry_on_idle_ms is not None and kwargs.get("ack_policy") in (
            AckPolicy.ACK,
            AckPolicy.ACK_FIRST,
        ):
            raise ValueError(
                "retry_on_idle_ms is incompatible with ack_policy=AckPolicy.ACK / "
                "AckPolicy.ACK_FIRST: those acknowledge messages even when the "
                "handler fails, so the PEL-based reclaimer never sees them and "
                "retries/DLQ never trigger. Use the default NACK_ON_ERROR."
            )

        # Default max_retries only applies when retry_on_idle_ms is set.
        if retry_on_idle_ms is None:
            max_retries = None

        stream_sub = StreamSub(
            channel,
            group=group,
            consumer=consumer,
            polling_interval=polling_interval,
            batch=batch,
            max_records=max_records,
            last_id=last_id,
            no_ack=no_ack,
            min_idle_time=min_idle_time,
        )

        # Track the subscription so the background monitor can recreate the
        # consumer group if Redis loses the stream (restart, failover, eviction).
        # Keep a reference so the retry block below can roll it back on failure.
        main_sub_info = None
        if group:
            main_sub_info = _StreamGroupInfo(
                stream_key=self._get_stream_key(channel),
                group=group,
                group_create_id="$" if last_id == ">" else last_id,
            )
            self._stream_subscriptions.add(main_sub_info)

        # Extract ack_policy or default to NACK_ON_ERROR for reliability
        # This ensures messages are NOT acknowledged when handlers raise exceptions,
        # allowing them to be redelivered for retry
        ack_policy = kwargs.pop("ack_policy", AckPolicy.NACK_ON_ERROR)

        # stream must be passed as keyword-only argument
        registered_handler = self.broker.subscriber(
            stream=stream_sub, ack_policy=ack_policy, **kwargs
        )(handler)

        if retry_on_idle_ms is not None and not _internal_retry:
            # Per-handler retry/dlq stream keys: when multiple handlers
            # subscribe to the same channel with different consumer groups,
            # each gets its own retry/dlq streams. A single shared retry
            # stream would broadcast one handler's failures to every other
            # handler on the channel via the auto-created `-retry` consumer
            # groups. See issue #225.
            # `Agent`/`Channel` always inject a unique handler_id (via the
            # HANDLERS_IDS counter), so the fallback only applies to callers that
            # use transport.subscribe() directly. getattr guards objects without a
            # __name__ (e.g. functools.partial), which would otherwise raise after
            # the main-stream subscriber is already registered. Direct callers that
            # run multiple distinct handlers on one channel with retry_on_idle_ms
            # should pass a distinct handler_id per handler — otherwise same-named
            # handlers (or lambdas) collapse to the same per-handler key. Derive
            # the name from the original handler, not the tracing wrapper.
            handler_name = (
                getattr(original_handler, "__name__", None)
                or type(original_handler).__name__
            )
            handler_suffix = handler_id if handler_id else f"{channel}-{handler_name}"
            retry_stream = f"{channel}.{handler_suffix}.retry"
            dlq_stream = (
                f"{channel}.{handler_suffix}.dlq" if max_retries is not None else None
            )
            retry_handler_id = f"{handler_suffix}-retry"

            # Set up the retry machinery transactionally: if any step below (incl.
            # the recursive retry subscribe) raises, roll back the in-memory
            # registrations this call made so a retried Agent.start() does not
            # accumulate orphaned reclaimer configs / stream-subscription entries.
            # The FastStream broker subscriber(s) cannot be un-registered, but
            # nothing is live until connect(), which never runs on failure.
            added_reclaimer_keys: list[tuple[str, str, str]] = []
            # The recursive subscribe below adds this entry (last_id=">" → "$").
            retry_sub_info = _StreamGroupInfo(
                stream_key=self._get_stream_key(retry_stream),
                group=retry_handler_id,
                group_create_id="$",
            )
            try:
                # Reclaimer for main stream: moves idle PEL entries to retry_stream
                # (or to dlq_stream if max_retries is exceeded).
                added_reclaimer_keys.append(
                    self._setup_reclaimer(
                        stream=channel,
                        group=group,
                        consumer=f"{group}-reclaimer",
                        retry_stream=retry_stream,
                        min_idle_ms=retry_on_idle_ms,
                        interval_s=retry_reclaim_interval_s,
                        max_retries=max_retries,
                        dlq_stream=dlq_stream,
                        on_dlq=on_dlq,
                        backoff_multiplier=retry_backoff_multiplier,
                        backoff_max_ms=retry_backoff_max_ms,
                        backoff_jitter=retry_backoff_jitter,
                    )
                )

                # Rebuild the same filter+trace stack against the retry stream:
                # tracing( filters( original_handler ) ), with the retry stream as the
                # tracing destination so retry-attempt spans report the retry stream
                # key rather than the original channel. Reclaimed messages re-enter as
                # raw dicts, so they must pass back through wrap_handler_with_filters
                # to be typed/filtered exactly like a first delivery. Wrapping the
                # original (not the channel-wrapped handler) keeps it to a single
                # consumer span per retry.
                from eggai.tracing import make_tracing_wrapper

                retry_handler = make_tracing_wrapper(
                    retry_stream,
                    wrap_handler_with_filters(original_handler, **filter_opts),
                )

                # Auto-subscribe the same handler to the retry stream.
                # _internal_retry=True prevents infinite recursion and .retry.retry
                # chains. last_id is pinned to ">" (new entries only) rather than
                # forwarding the caller's last_id: an operator replaying the main
                # stream (e.g. last_id="0") must not also replay the retry stream's
                # history — the retry stream only ever holds freshly-reclaimed entries.
                #
                # `group` is pinned to retry_handler_id (stable across workers) but
                # `consumer` is deliberately omitted so it defaults to the
                # per-process-unique name — otherwise a worker fleet would conflate
                # the retry stream's PEL under one consumer name, undercutting the
                # competing-consumers behaviour for retried messages.
                await self.subscribe(
                    retry_stream,
                    retry_handler,
                    _internal_retry=True,
                    handler_id=retry_handler_id,
                    group=retry_handler_id,
                    polling_interval=polling_interval,
                    batch=batch,
                    max_records=max_records,
                    last_id=">",
                    no_ack=no_ack,
                    ack_policy=ack_policy,
                    **kwargs,
                )

                # Reclaimer for retry stream: re-queues back to the same retry
                # stream (avoids creating a .retry.retry chain). Routes to DLQ if
                # max_retries is exceeded.
                added_reclaimer_keys.append(
                    self._setup_reclaimer(
                        stream=retry_stream,
                        group=retry_handler_id,
                        consumer=f"{retry_handler_id}-reclaimer",
                        retry_stream=retry_stream,
                        min_idle_ms=retry_on_idle_ms,
                        interval_s=retry_reclaim_interval_s,
                        max_retries=max_retries,
                        dlq_stream=dlq_stream,
                        on_dlq=on_dlq,
                        backoff_multiplier=retry_backoff_multiplier,
                        backoff_max_ms=retry_backoff_max_ms,
                        backoff_jitter=retry_backoff_jitter,
                    )
                )
            except Exception:
                # Undo the reversible state this call registered, then re-raise.
                if main_sub_info is not None:
                    self._stream_subscriptions.discard(main_sub_info)
                self._stream_subscriptions.discard(retry_sub_info)
                if self._reclaimer_manager is not None:
                    for key in added_reclaimer_keys:
                        self._reclaimer_manager.discard(key)
                raise

        return registered_handler

    async def _monitor_stream_groups(self) -> None:
        """Periodically ensure all registered stream consumer groups exist.

        When Redis loses streams (restart, failover, eviction), FastStream's
        consume loop retries xreadgroup but never re-runs xgroup_create.
        This monitor closes that gap by periodically attempting xgroup_create
        for every registered subscription.  The call raises BUSYGROUP when the
        group already exists, making it cheap under normal operation.

        Uses id="0" when the stream still has entries (partial group loss) so
        unprocessed messages are redelivered.  Falls back to the original
        group_create_id with MKSTREAM when the stream itself is gone.
        """
        client = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            while self._running:
                await asyncio.sleep(self._group_monitor_interval_s)
                # Iterate a snapshot: a concurrent subscribe() on a shared
                # transport may mutate the set between awaits below.
                for info in list(self._stream_subscriptions):
                    try:
                        stream_exists = await client.exists(info.stream_key)
                        create_id = "0" if stream_exists else info.group_create_id
                        await client.xgroup_create(
                            name=info.stream_key,
                            groupname=info.group,
                            id=create_id,
                            mkstream=True,
                        )
                        logger.info(
                            "Recreated missing consumer group %s on stream %s (id=%s)",
                            info.group,
                            info.stream_key,
                            create_id,
                        )
                    except ResponseError as e:
                        if "BUSYGROUP" not in str(e):
                            logger.warning(
                                "Failed to ensure consumer group %s on %s: %s",
                                info.group,
                                info.stream_key,
                                e,
                            )
        except asyncio.CancelledError:
            pass
        finally:
            await client.aclose()

    def _setup_reclaimer(
        self,
        *,
        stream: str,
        group: str,
        consumer: str,
        retry_stream: str,
        min_idle_ms: int,
        interval_s: float,
        max_retries: int | None = None,
        dlq_stream: str | None = None,
        on_dlq: Callable | None = None,
        backoff_multiplier: float = 1.0,
        backoff_max_ms: int | None = None,
        backoff_jitter: float = 0.0,
    ) -> tuple[str, str, str]:
        if self._reclaimer_manager is None:
            self._reclaimer_manager = PendingReclaimerManager(self._redis_url)
        return self._reclaimer_manager.add(
            ReclaimerConfig(
                stream=self._get_stream_key(stream),
                group=group,
                consumer=consumer,
                retry_stream=self._get_stream_key(retry_stream),
                min_idle_ms=min_idle_ms,
                interval_s=interval_s,
                max_retries=max_retries,
                dlq_stream=self._get_stream_key(dlq_stream) if dlq_stream else None,
                on_dlq=on_dlq,
                max_len=self._retry_max_len,
                backoff_multiplier=backoff_multiplier,
                backoff_max_ms=backoff_max_ms,
                backoff_jitter=backoff_jitter,
            )
        )

    @staticmethod
    def _get_stream_key(channel: str) -> str:
        if channel.startswith("eggai."):
            return channel
        return f"eggai.{channel}"
