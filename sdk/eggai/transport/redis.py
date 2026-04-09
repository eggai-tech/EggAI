import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from faststream import AckPolicy
from faststream.redis import RedisBroker, StreamSub
from redis.exceptions import ResponseError

from eggai.schemas import BaseMessage
from eggai.transport.base import Transport
from eggai.transport.middleware_utils import (
    create_data_type_middleware,
    create_filter_by_data_middleware,
    create_filter_middleware,
)
from eggai.transport.pending_reclaimer import PendingReclaimerManager, ReclaimerConfig

logger = logging.getLogger(__name__)


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
        **kwargs,
    ):
        """
        Initializes the RedisTransport with an optional RedisBroker or creates a new one with provided URL.

        Args:
            broker (Optional[RedisBroker]): An existing RedisBroker instance to use. If not provided, a new instance will
                                             be created with the specified URL and additional parameters.
            url (str): The Redis connection URL (default is "redis://localhost:6379").
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
        self._running = False
        self._reclaimer_manager: PendingReclaimerManager | None = None
        self._stream_subscriptions: list[_StreamGroupInfo] = []
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
        await self.broker.start()
        if self._reclaimer_manager is not None:
            await self._reclaimer_manager.start()
        self._running = True
        if self._stream_subscriptions:
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
        await self.broker.publish(message, stream=channel)

    async def subscribe(self, channel: str, handler, **kwargs) -> Callable:
        """
        Subscribes to a Redis channel and sets up a handler to process incoming messages.

        Args:
            channel (str): The Redis channel to subscribe to.
            handler (Callable): The function or coroutine that will handle messages received from the channel.
            **kwargs: Additional keyword arguments that can be used to configure the subscription.

        Keyword Args:
            filter_by_message (Callable, optional): A function to filter incoming messages based on their payload. If provided,
                                                this function will be applied to the message payload before passing it to
                                                the handler.
            data_type (BaseModel, optional): A Pydantic model class to validate and filter incoming messages by type.
            filter_by_data (Callable, optional): A function to filter typed messages after validation (requires `data_type`).

            # Redis Pub/Sub parameters
            pattern (bool, optional): Whether to use pattern-based subscription (default is False).

            # Redis Stream parameters
            stream (Optional[str], optional): Redis stream name to consume from instead of Pub/Sub channel.
            polling_interval (int, optional): Interval in milliseconds for polling streams (default is 100).
            group (Optional[str], optional): Consumer group name for stream consumption.
            consumer (Optional[str], optional): Consumer name within the group.
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
                this threshold are moved to a dedicated ``{channel}.retry`` stream and re-delivered to the same handler.
                Mutually exclusive with min_idle_time. Recommended: 30_000 (30 seconds).
                Delivery is at-least-once — handlers must be idempotent. Injected fields _retry_count and
                _original_message_id can be used for deduplication.
                Binary (non-UTF-8) field values are not supported.
            retry_reclaim_interval_s (float, optional): How often the reclaimer scans for stuck messages (default 15.0s).
                Only used when retry_on_idle_ms is set.
            max_retries (int, optional): Maximum number of retry attempts before routing to the Dead Letter Queue
                (``{channel}.dlq``). Default is 5 when retry_on_idle_ms is set. With max_retries=5, the handler is
                called up to 6 times total (1 original + 5 retries). Set to None for unlimited retries (no DLQ).
                Requires retry_on_idle_ms.
            on_dlq (Callable, optional): Callback invoked when a message is routed to the DLQ. Can be sync or async.
                Signature: ``on_dlq(fields: dict, msg_id: str, retry_count: int)``. Errors in the callback are
                logged but never prevent the DLQ write. Only used when retry_on_idle_ms and max_retries are set.
            retry_on_error (bool, optional): Whether to retry handler on error (default is True).

            # Durability parameters
            max_len (Optional[int], optional): Maximum stream length to prevent unbounded growth (default is None).
                                               Recommend setting to a reasonable value like 10000 for production.

            # General parameters
            dependencies (Sequence[Depends], optional): Custom dependencies for this subscriber.
            middlewares (Sequence[BrokerMiddleware], optional): Custom middlewares for this subscriber.
            filter (Filter, optional): Message filter configuration.
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
        _internal_retry = kwargs.pop("_internal_retry", False)

        # Only wrap the handler on the initial subscribe call, not on the
        # internal recursive call for the retry stream — otherwise the retry
        # handler gets double-wrapped, producing duplicate spans and corrupting
        # the consumer group name (handler.__name__ becomes "traced_handler").
        if not _internal_retry:
            from eggai.tracing import make_tracing_wrapper

            handler = make_tracing_wrapper(channel, handler)

        if "filter_by_message" in kwargs:
            if "middlewares" not in kwargs:
                kwargs["middlewares"] = []
            kwargs["middlewares"].append(
                create_filter_middleware(kwargs.pop("filter_by_message"))
            )

        if "data_type" in kwargs:
            data_type = kwargs.pop("data_type")

            if "middlewares" not in kwargs:
                kwargs["middlewares"] = []
            kwargs["middlewares"].append(create_data_type_middleware(data_type))

            if "filter_by_data" in kwargs:
                if "middlewares" not in kwargs:
                    kwargs["middlewares"] = []
                kwargs["middlewares"].append(
                    create_filter_by_data_middleware(
                        data_type, kwargs.pop("filter_by_data")
                    )
                )

        handler_id = kwargs.pop("handler_id", None)

        # Ignore Kafka-specific parameter (Redis uses 'group' for streams, not 'group_id')
        kwargs.pop("group_id", None)

        # Extract stream-related parameters
        group = kwargs.pop("group", handler_id)
        consumer = kwargs.pop("consumer", handler_id)
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
        if group:
            self._stream_subscriptions.append(
                _StreamGroupInfo(
                    stream_key=self._get_stream_key(channel),
                    group=group,
                    group_create_id="$" if last_id == ">" else last_id,
                )
            )

        # Extract ack_policy or default to NACK_ON_ERROR for reliability
        # This ensures messages are NOT acknowledged when handlers raise exceptions,
        # allowing them to be redelivered for retry
        ack_policy = kwargs.pop("ack_policy", AckPolicy.NACK_ON_ERROR)

        # stream must be passed as keyword-only argument
        registered_handler = self.broker.subscriber(
            stream=stream_sub, ack_policy=ack_policy, **kwargs
        )(handler)

        if retry_on_idle_ms is not None and not _internal_retry:
            retry_stream = f"{channel}.retry"
            dlq_stream = f"{channel}.dlq" if max_retries is not None else None
            retry_handler_id = (
                f"{handler_id}-retry"
                if handler_id
                else f"{channel}-{handler.__name__}-retry"
            )

            # Reclaimer for main stream: moves idle PEL entries to retry_stream
            # (or to dlq_stream if max_retries is exceeded).
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
            )

            # Auto-subscribe the same handler to the retry stream.
            # _internal_retry=True prevents infinite recursion and .retry.retry chains.
            await self.subscribe(
                retry_stream,
                handler,
                _internal_retry=True,
                handler_id=retry_handler_id,
                group=retry_handler_id,
                consumer=retry_handler_id,
                polling_interval=polling_interval,
                batch=batch,
                max_records=max_records,
                last_id=last_id,
                no_ack=no_ack,
                ack_policy=ack_policy,
                **kwargs,
            )

            # Reclaimer for retry stream: re-queues back to the same retry stream
            # (avoids creating a .retry.retry chain). Routes to DLQ if max_retries
            # is exceeded.
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
            )

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
                for info in self._stream_subscriptions:
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
    ) -> None:
        if self._reclaimer_manager is None:
            self._reclaimer_manager = PendingReclaimerManager(self._redis_url)
        self._reclaimer_manager.add(
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
            )
        )

    @staticmethod
    def _get_stream_key(channel: str) -> str:
        if channel.startswith("eggai."):
            return channel
        return f"eggai.{channel}"
