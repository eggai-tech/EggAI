import socket

import pytest


def is_service_available(host, port, timeout=1):
    """Check if a service is available at host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests if services aren't available."""
    kafka_available = is_service_available("localhost", 9092)
    redis_available = is_service_available("localhost", 6379)

    skip_kafka = pytest.mark.skip(reason="Kafka not available at localhost:9092")
    skip_redis = pytest.mark.skip(reason="Redis not available at localhost:6379")

    for item in items:
        # Skip Kafka tests
        if "kafka" in str(item.fspath).lower() or "kafka" in item.nodeid.lower():
            if not kafka_available:
                item.add_marker(skip_kafka)

        # Skip Redis tests
        if "redis" in str(item.fspath).lower() or "redis" in item.nodeid.lower():
            if not redis_available:
                item.add_marker(skip_redis)

        # Skip tests that use KafkaTransport in their code
        if not kafka_available:
            try:
                if hasattr(item, "obj"):
                    import inspect

                    source = inspect.getsource(item.obj)
                    if "KafkaTransport" in source:
                        item.add_marker(skip_kafka)
            except (TypeError, OSError):
                pass
