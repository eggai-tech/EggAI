import asyncio
import os
import random
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import aiohttp

from libraries.logger import get_console_logger

from .models import ParameterCombination, RetrievalResult, RetrievalTestCase

logger = get_console_logger("retrieval_api_client")


class RetrievalAPIClient:
    """Client for testing retrieval API with embedded service."""

    def __init__(self):
        self.port = self._find_available_port()
        self.base_url = f"http://localhost:{self.port}"
        self.process: Optional[subprocess.Popen] = None

    def _find_available_port(self) -> int:
        """Find an available port in the range 10000-11000."""
        for _ in range(100):  # Try up to 100 random ports
            port = random.randint(10000, 11000)
            if not self.is_port_in_use(port):
                return port
        raise RuntimeError("Could not find an available port in range 10000-11000")

    def is_port_in_use(self, port: int) -> bool:
        """Check if port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            return sock.connect_ex(("localhost", port)) == 0

    async def check_api_health(self) -> bool:
        """Check API health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") == "healthy"
                    return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def start_service(self) -> bool:
        """Start the embedded service."""
        logger.info(f"Starting service on port {self.port}")

        current_file = Path(__file__).resolve()
        project_root = None

        for parent in current_file.parents:
            if (parent / "agents").exists():
                project_root = parent
                break

        if not project_root:
            raise RuntimeError(
                "Could not find project root directory with agents/ folder"
            )

        # Inherit environment from parent process
        env = os.environ.copy()
        env["POLICIES_API_HOST"] = "localhost"
        env["POLICIES_API_PORT"] = str(self.port)

        cmd = [sys.executable, "-m", "agents.policies.agent.main"]

        # Log the exact command being run for debugging
        logger.info(f"Starting command: {' '.join(cmd)}")
        logger.info(f"Working directory: {project_root}")
        logger.info(f"Environment overrides: POLICIES_API_HOST={env.get('POLICIES_API_HOST')}, POLICIES_API_PORT={env.get('POLICIES_API_PORT')}")
        
        self.process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout for easier debugging
        )

        # Wait for service to be ready
        for i in range(60):  # Wait up to 60 seconds
            await asyncio.sleep(1)

            # Check if process is still alive
            if self.process.poll() is not None:
                exit_code = self.process.poll()
                logger.error(f"Process died early with exit code {exit_code}")
                
                # Log process output for debugging
                try:
                    stdout, _ = self.process.communicate(timeout=1)
                    if stdout:
                        logger.error(f"Process output: {stdout.decode()}")
                except Exception as e:
                    logger.error(f"Could not read process output: {e}")
                break

            if await self.check_api_health():
                logger.info(f"Service started successfully on port {self.port}")
                return True

            if i % 10 == 0:  # Log progress every 10 seconds
                logger.info(f"Waiting for service to start... ({i}/60 seconds)")

        logger.error("Service failed to start within timeout")
        
        # Try to get final process output before stopping
        if self.process and self.process.poll() is not None:
            try:
                stdout, _ = self.process.communicate(timeout=1)
                if stdout:
                    logger.error(f"Final process output: {stdout.decode()}")
            except Exception as e:
                logger.error(f"Could not read final process output: {e}")
        
        self.stop_service()
        return False

    def stop_service(self):
        """Stop the embedded service."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
            logger.info(f"Service stopped on port {self.port}")

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
                    f"{self.base_url}/api/v1/kb/search/vector",
                    json=search_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    retrieval_time_ms = (time.perf_counter() - start_time) * 1000

                    if response.status == 200:
                        response_data = await response.json()
                        retrieved_chunks = self._extract_chunks(response_data)
                        total_hits = response_data.get("total_hits", len(retrieved_chunks))
                        
                        # Debug logging
                        logger.info(f"Query: '{test_case.question[:50]}...' | Category: {test_case.category} | Search: {combination.search_type} | Hits: {total_hits}")
                        if total_hits == 0:
                            logger.warning(f"Zero hits for query. Response keys: {list(response_data.keys())}")

                        return RetrievalResult(
                            combination=combination,
                            retrieved_chunks=retrieved_chunks,
                            retrieval_time_ms=retrieval_time_ms,
                            total_hits=total_hits,
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
