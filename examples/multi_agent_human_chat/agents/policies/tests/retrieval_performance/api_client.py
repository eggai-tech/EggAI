import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import aiohttp

from libraries.logger import get_console_logger

from .models import ParameterCombination, RetrievalResult, RetrievalTestCase

logger = get_console_logger("retrieval_api_client")


class RetrievalAPIClient:
    """Client for testing retrieval API."""

    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url

    def is_port_in_use(self, port: int) -> bool:
        """Check if port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            return sock.connect_ex(("localhost", port)) == 0

    async def check_api_health(self) -> bool:
        """Check API health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") == "healthy"
                    return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def ensure_api_running(self) -> bool:
        """Ensure API is running, start if needed."""
        if await self.check_api_health():
            logger.info(f"API is already running and healthy at {self.base_url}")
            return True

        port = int(self.base_url.split(":")[-1])
        if self.is_port_in_use(port):
            logger.warning(f"Port {port} is in use but API is not responding properly")
            await asyncio.sleep(2)
            if await self.check_api_health():
                logger.info("API became healthy after waiting")
                return True
            else:
                logger.error("Port is busy but API is not healthy - cannot start test")
                return False

        return await self._start_api(port)

    async def _start_api(self, port: int) -> bool:
        """Start the API server."""
        logger.info(f"Starting API server on port {port}")
        try:
            current_file = Path(__file__).resolve()
            project_root = None

            for parent in current_file.parents:
                if (parent / "agents").exists():
                    project_root = parent
                    break

            if not project_root:
                logger.error(
                    "Could not find project root directory with agents/ folder"
                )
                return False

            process = subprocess.Popen(
                [sys.executable, "-m", "agents.policies.agent.main"],
                cwd=str(project_root),
            )

            # Wait for server to start
            for _ in range(30):
                await asyncio.sleep(1)
                if await self.check_api_health():
                    logger.info("API server started successfully")
                    return True

            logger.error("API server failed to start within timeout")
            process.terminate()
            return False

        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            return False

    async def query_single(
        self, combination: ParameterCombination, test_case: RetrievalTestCase
    ) -> RetrievalResult:
        """Execute single retrieval query."""
        start_time = time.perf_counter()

        try:
            search_payload = {
                "query": test_case.question,
                "category": test_case.category,
                "max_hits": combination.max_hits,
                "search_type": combination.search_type,
                "alpha": 0.7,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/kb/search",
                    json=search_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    retrieval_time_ms = (time.perf_counter() - start_time) * 1000

                    if response.status == 200:
                        response_data = await response.json()
                        retrieved_chunks = self._extract_chunks(response_data)

                        return RetrievalResult(
                            combination=combination,
                            retrieved_chunks=retrieved_chunks,
                            retrieval_time_ms=retrieval_time_ms,
                            total_hits=response_data.get(
                                "total_hits", len(retrieved_chunks)
                            ),
                        )
                    else:
                        error_text = await response.text()
                        return RetrievalResult(
                            combination=combination,
                            retrieved_chunks=[],
                            retrieval_time_ms=retrieval_time_ms,
                            total_hits=0,
                            error=f"HTTP {response.status}: {error_text}",
                        )

        except Exception as e:
            retrieval_time_ms = (time.perf_counter() - start_time) * 1000
            return RetrievalResult(
                combination=combination,
                retrieved_chunks=[],
                retrieval_time_ms=retrieval_time_ms,
                total_hits=0,
                error=str(e),
            )

    def _extract_chunks(self, response_data: dict) -> List[dict]:
        """Extract document chunks from API response."""
        retrieved_chunks = []
        for doc in response_data.get("documents", []):
            retrieved_chunks.append(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "text": doc.get("text"),
                    "category": doc.get("category"),
                    "chunk_index": doc.get("chunk_index"),
                    "source_file": doc.get("source_file"),
                    "relevance": doc.get("relevance"),
                    "page_numbers": doc.get("page_numbers", []),
                    "page_range": doc.get("page_range"),
                    "headings": doc.get("headings", []),
                    "citation": doc.get("citation"),
                    "document_id": doc.get("document_id"),
                    "previous_chunk_id": doc.get("previous_chunk_id"),
                    "next_chunk_id": doc.get("next_chunk_id"),
                    "chunk_position": doc.get("chunk_position"),
                }
            )
        return retrieved_chunks
