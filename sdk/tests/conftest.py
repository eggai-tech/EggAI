import pytest
from eggai.transport.inmemory import InMemoryTransport

@pytest.fixture(autouse=True)
def reset_inmemory_transport():
    InMemoryTransport._CHANNELS.clear()
    InMemoryTransport._SUBSCRIPTIONS.clear()
    yield
    InMemoryTransport._CHANNELS.clear()
    InMemoryTransport._SUBSCRIPTIONS.clear()
