import json
import logging
from typing import Dict, Any, Optional, Callable, Union, Awaitable

from faststream.broker.message import StreamMessage
from faststream.kafka import KafkaBroker

from eggai.schemas import BaseMessage
from eggai.transport.base import Transport


class KafkaTransport(Transport):
    """
    Kafka-based transport layer adapted to use FastStream's KafkaBroker for message publishing and consumption.

    This class serves as a transport mechanism that integrates with Kafka to allow message publishing
    and consumption. It uses the FastStream KafkaBroker to interact with Kafka, offering methods to
    connect, disconnect, publish messages to Kafka topics, and subscribe to Kafka topics.

    Attributes:
        broker (KafkaBroker): The KafkaBroker instance responsible for managing Kafka connections and messaging.
    """

    def __init__(
        self,
        broker: Optional[KafkaBroker] = None,
        bootstrap_servers: str = "localhost:19092",
        **kwargs,
    ):
        """
        Initializes the KafkaTransport with an optional KafkaBroker or creates a new one with provided bootstrap servers.

        Args:
            broker (Optional[KafkaBroker]): An existing KafkaBroker instance to use. If not provided, a new instance will
                                             be created with the specified bootstrap servers and additional parameters.
            bootstrap_servers (str): The Kafka bootstrap server addresses (default is "localhost:19092").
            **kwargs: Additional keyword arguments to pass to the KafkaBroker if a new instance is created.

        Attributes:
            bootstrap_servers (Union[str, Iterable[str]]): A list or string of `host[:port]` addresses of brokers to contact for
                                                          bootstrap. Default is `"localhost"`.\n\n
            request_timeout_ms (int): Client request timeout in milliseconds (default is 40,000 ms).
            retry_backoff_ms (int): Milliseconds to back off when retrying on errors (default is 100 ms).
            metadata_max_age_ms (int): Period after which to refresh metadata (default is 300,000 ms).
            connections_max_idle_ms (int): Close idle connections after a specified time (default is 540,000 ms).
            sasl_kerberos_service_name (str): Kerberos service name (default is `"kafka"`).
            sasl_kerberos_domain_name (Optional[str]): Kerberos domain name.
            sasl_oauth_token_provider (Optional[AbstractTokenProvider]): OAuthBearer token provider instance.
            loop (Optional[AbstractEventLoop]): Optional event loop.
            client_id (Optional[str]): A name for this client (default is `"SERVICE_NAME"`).
            acks (Union[Literal[0, 1, -1, "all"], object]): Number of acknowledgments the producer requires before considering
                                                       a request complete (default is `None`).
            key_serializer (Optional[Callable[[Any], bytes]]): Function to serialize keys (default is `None`).
            value_serializer (Optional[Callable[[Any], bytes]]): Function to serialize values (default is `None`).
            compression_type (Optional[Literal["gzip", "snappy", "lz4", "zstd"]]): Compression type (default is `None`).
            max_batch_size (int): Maximum size of buffered data per partition (default is 16 KB).
            partitioner (Callable[[bytes, List[Partition], List[Partition]], Partition]): Partitioner function for assigning messages to partitions.
            max_request_size (int): Maximum size of a request (default is 1 MB).
            linger_ms (int): Time to delay requests for batching (default is 0 ms).
            enable_idempotence (bool): Whether to enable idempotence for the producer (default is `False`).
            transactional_id (Optional[str]): Transactional ID for producing messages (default is `None`).
            transaction_timeout_ms (int): Timeout for transactions (default is 60,000 ms).
            graceful_timeout (Optional[float]): Graceful shutdown timeout (default is 15.0).
            decoder (Optional[CustomCallable]): Custom decoder for messages (default is `None`).
            parser (Optional[CustomCallable]): Custom parser for messages (default is `None`).
            dependencies (Iterable[Depends]): Dependencies to apply to all broker subscribers (default is `()`).
            middlewares (Sequence[Union["BrokerMiddleware[ConsumerRecord]", "BrokerMiddleware[Tuple[ConsumerRecord, ...]]"]]):
                         Middlewares to apply to all broker publishers/subscribers (default is `()`).
            security (Optional[BaseSecurity]): Security options for broker connection (default is `None`).
            asyncapi_url (Union[str, Iterable[str], None]): AsyncAPI server URL (default is `None`).
            protocol (Optional[str]): AsyncAPI server protocol (default is `None`).
            protocol_version (Optional[str]): AsyncAPI server protocol version (default is `"auto"`).
            description (Optional[str]): AsyncAPI server description (default is `None`).
            tags (Optional[Iterable[Union["asyncapi.Tag", "asyncapi.TagDict"]]]): AsyncAPI server tags (default is `None`).
            logger (Optional[LoggerProto]): Custom logger to pass into context (default is `EMPTY`).
            log_level (int): Log level for service messages (default is `logging.INFO`).
            log_fmt (Optional[str]): Log format (default is `None`).
        """
        if broker:
            self.broker = broker
        else:
            self.broker = KafkaBroker(
                bootstrap_servers, log_level=logging.DEBUG, **kwargs
            )

    async def connect(self):
        """
        Establishes a connection to the Kafka broker by starting the KafkaBroker instance.

        This method is necessary before publishing or consuming messages. It asynchronously starts the broker
        to handle Kafka communication.

        """
        await self.broker.start()

    async def disconnect(self):
        """
        Closes the connection to the Kafka broker by closing the KafkaBroker instance.

        This method should be called when the transport is no longer needed to stop consuming messages
        and to release any resources held by the KafkaBroker.
        """
        await self.broker.close()

    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
        """
        Publishes a message to the specified Kafka topic (channel).

        Args:
            channel (str): The name of the Kafka topic to which the message will be published.
            message (Union[Dict[str, Any], BaseMessage]): The message to publish, which can either be a dictionary
                                                         or a BaseMessage instance. The message will be serialized
                                                         before being sent.

        """
        await self.broker.publish(message, topic=channel)

    async def subscribe(self, channel: str, handler, **kwargs) -> Callable:
        """
        Subscribes to a Kafka topic (channel) and sets up a handler to process incoming messages.

        Args:
            channel (str): The Kafka topic to subscribe to.
            handler (Callable): The function or coroutine that will handle messages received from the topic.
            **kwargs: Additional keyword arguments that can be used to configure the subscription.

        Keyword Args:
            filter_by_message (Callable, optional): A function to filter incoming messages based on their payload. If provided,
                                                this function will be applied to the message payload before passing it to
                                                the handler.
            batch (bool, optional): Whether to consume messages in batches or not (default is False).
            group_id (Optional[str], optional): The consumer group name for dynamic partition assignment and offset management.
            key_deserializer (Optional[Callable], optional): A function to deserialize the message key from raw bytes.
            value_deserializer (Optional[Callable], optional): A function to deserialize the message value from raw bytes.
            fetch_max_bytes (int, optional): The maximum amount of data the server should return for a fetch request (default is 50 MB).
            fetch_min_bytes (int, optional): The minimum amount of data the server should return for a fetch request (default is 1 byte).
            fetch_max_wait_ms (int, optional): The maximum amount of time the server will block before responding to a fetch request (default is 500 ms).
            max_partition_fetch_bytes (int, optional): The maximum amount of data per-partition the server will return (default is 1 MB).
            auto_offset_reset (str, optional): A policy for resetting offsets on `OffsetOutOfRangeError` errors (default is 'latest').
            auto_commit (bool, optional): Whether to automatically commit offsets (default is True).
            auto_commit_interval_ms (int, optional): Interval in milliseconds between automatic offset commits (default is 5000 ms).
            check_crcs (bool, optional): Whether to check CRC32 of records to ensure message integrity (default is True).
            partition_assignment_strategy (Sequence, optional): List of strategies for partition assignment during group management (default is `RoundRobinPartitionAssignor`).
            max_poll_interval_ms (int, optional): Maximum allowed time between calls to consume messages in batches (default is 300000 ms).
            rebalance_timeout_ms (Optional[int], optional): Timeout for consumer rejoin during rebalance (default is None).
            session_timeout_ms (int, optional): Client group session timeout (default is 10000 ms).
            heartbeat_interval_ms (int, optional): The interval between heartbeats to the consumer coordinator (default is 3000 ms).
            consumer_timeout_ms (int, optional): Maximum wait timeout for background fetching routine (default is 200 ms).
            max_poll_records (Optional[int], optional): The maximum number of records to fetch in one batch (default is None).
            exclude_internal_topics (bool, optional): Whether to exclude internal topics such as offsets from being exposed to the consumer (default is True).
            isolation_level (str, optional): Controls how to read messages written transactionally ('read_uncommitted' or 'read_committed', default is 'read_uncommitted').
            batch_timeout_ms (int, optional): Milliseconds to wait for data in the buffer if no data is available (default is 200 ms).
            max_records (Optional[int], optional): Number of messages to consume in one batch (default is None).
            listener (Optional[ConsumerRebalanceListener], optional): Optionally provide a listener for consumer group rebalances (default is None).
            pattern (Optional[str], optional): Pattern to match available topics (either this or `topics` must be provided, not both).
            partitions (Collection[TopicPartition], optional): Explicit list of partitions to assign (can't use with `topics`).

        Returns:
            Callable: A callback function that represents the subscription. When invoked, it will call the handler with
                      incoming messages.
        """
        if "filter_by_message" in kwargs:

            def filter_middleware(filter_func):
                async def middleware(
                    call_next: Callable[[Any], Awaitable[Any]],
                    msg: StreamMessage[Any],
                ) -> Any:
                    if filter_func(json.loads(msg.body.decode("utf-8"))):
                        return await call_next(msg)
                    return None

                return middleware

            if "middlewares" not in kwargs:
                kwargs["middlewares"] = []
            kwargs["middlewares"].append(
                filter_middleware(kwargs.pop("filter_by_message"))
            )

        if "data_type" in kwargs:
            data_type = kwargs.pop("data_type")

            def data_type_middleware(data_type):
                async def middleware(
                    call_next: Callable[[Any], Awaitable[Any]],
                    msg: StreamMessage[Any],
                ) -> Any:
                    typed_message = data_type.model_validate(
                        json.loads(msg.body.decode("utf-8"))
                    )

                    if typed_message.type != data_type.model_fields["type"].default:
                        return None

                    return await call_next(msg)

                return middleware

            if "middlewares" not in kwargs:
                kwargs["middlewares"] = []
            kwargs["middlewares"].append(data_type_middleware(data_type))

            if "filter_by_data" in kwargs:

                def filter_by_data_middleware(filter_func):
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

                if "middlewares" not in kwargs:
                    kwargs["middlewares"] = []
                kwargs["middlewares"].append(
                    filter_by_data_middleware(kwargs.pop("filter_by_data"))
                )

        handler_id = kwargs.pop("handler_id")
        if "group_id" not in kwargs:
            kwargs["group_id"] = handler_id

        if "pattern" in kwargs:
            return self.broker.subscriber(**kwargs)(handler)
        else:
            return self.broker.subscriber(channel, **kwargs)(handler)
