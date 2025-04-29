import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Ensure a fresh event loop for the test session to avoid 'RuntimeError: Event loop is closed'."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
