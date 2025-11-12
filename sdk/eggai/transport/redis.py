import json
import logging
from typing import Dict, Any, Optional, Callable, Union, Awaitable

from faststream.broker.message import StreamMessage
from faststream.redis import RedisBroker, StreamSub

from eggai.schemas import BaseMessage
from eggai.transport.base import Transport


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
        broker: Optional[RedisBroker] = None,
        url: str = "redis://localhost:6379",
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
            self.broker = RedisBroker(
                url, log_level=logging.DEBUG, **kwargs
            )

    async def connect(self):
        """
        Establishes a connection to the Redis server by starting the RedisBroker instance.

        This method is necessary before publishing or consuming messages. It asynchronously starts the broker
        to handle Redis communication.

        """
        await self.broker.start()

    async def disconnect(self):
        """
        Closes the connection to the Redis server by closing the RedisBroker instance.

        This method should be called when the transport is no longer needed to stop consuming messages
        and to release any resources held by the RedisBroker.
        """
        await self.broker.close()

    async def publish(self, channel: str, message: Union[Dict[str, Any], BaseMessage]):
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
            polling_interval (int, optional): Interval in seconds for polling streams (default is 1).
            group (Optional[str], optional): Consumer group name for stream consumption.
            consumer (Optional[str], optional): Consumer name within the group.
            batch (bool, optional): Whether to consume messages in batches (default is False).
            max_records (Optional[int], optional): Maximum number of records to consume in one batch (default is None).
            last_id (str, optional): Starting message ID for stream consumption (default is "$" for new messages).
            no_ack (bool, optional): Whether to skip acknowledgment of stream messages (default is False).
            retry_on_error (bool, optional): Whether to retry handler on error (default is True).

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

        # Extract stream-related parameters
        group = kwargs.pop("group", handler_id)
        consumer = kwargs.pop("consumer", handler_id)
        polling_interval = kwargs.pop("polling_interval", 100)
        batch = kwargs.pop("batch", False)
        max_records = kwargs.pop("max_records", None)
        last_id = kwargs.pop("last_id", "$")
        no_ack = kwargs.pop("no_ack", False)

        # Use Redis Streams with consumer groups (similar to Kafka)
        # Each handler with a unique group will receive all messages
        stream_sub = StreamSub(
            channel,
            group=group,
            consumer=consumer,
            polling_interval=polling_interval,
            batch=batch,
            max_records=max_records,
            last_id=last_id,
            no_ack=no_ack
        )

        # stream must be passed as keyword-only argument
        return self.broker.subscriber(stream=stream_sub, **kwargs)(handler)
