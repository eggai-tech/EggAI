import asyncio
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Ensure a fresh event loop for the test session to avoid 'RuntimeError: Event loop is closed'."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_rag_index():
    """Ensure the RAG index is initialized before running tests."""
    from agents.policies.rag.init_index import init_policies_index
    
    # Check if index exists
    current_dir = Path(__file__).parent.parent / "rag"
    index_path = current_dir / ".ragatouille" / "colbert" / "indexes" / "policies_index"
    metadata_path = index_path / "metadata.json"
    
    if not index_path.exists() or not metadata_path.exists():
        print("RAG index not found, initializing...")
        try:
            success = init_policies_index(force_rebuild=False)
            if success:
                print("RAG index initialized successfully")
            else:
                print("RAG index initialization failed, tests will use mock retrieval")
        except Exception as e:
            print(f"RAG index initialization failed: {e}, tests will use mock retrieval")
    else:
        print("RAG index already exists")
