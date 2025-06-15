#!/usr/bin/env python3
"""
Test script for Temporal integration with Policy Documentation RAG.

This script demonstrates how to use the Temporal client to execute
policy documentation queries via workflows.

Key components demonstrated:
1. Connecting to Temporal server
2. Executing workflows with different parameters
3. Parallel workflow execution
4. Handling workflow results
"""

import asyncio
import sys
import time
from typing import Any, Dict, List

import pytest

from agents.policies.rag.documentation_temporal_client import (
    DocumentationTemporalClient,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.test_temporal")

@pytest.mark.asyncio
async def test_sequential_queries():
    """Test sequential documentation queries using Temporal workflows."""
    client = DocumentationTemporalClient()
    
    try:
        # Test 1: Basic query without category filter
        logger.info("TEST 1: Basic query without category filter")
        result = await client.query_documentation_async(
            query="What is covered under fire damage?",
            policy_category="",
        )
        
        log_result(result.results, "No category filter")
        
        # Test 2: Query with home category filter
        logger.info("TEST 2: Query with 'Home' category filter")
        result = await client.query_documentation_async(
            query="What is the deductible?",
            policy_category="Home",
        )
        
        log_result(result.results, "With 'Home' category filter")
        
        # Test 3: Query with auto category filter
        logger.info("TEST 3: Query with 'Auto' category filter")
        result = await client.query_documentation_async(
            query="What is covered in a collision?",
            policy_category="Auto",
        )
        
        log_result(result.results, "With 'Auto' category filter")
        
        return True
    except Exception as e:
        logger.error(f"Sequential query test failed: {e}", exc_info=True)
        return False
    finally:
        await client.close()

@pytest.mark.asyncio
async def test_parallel_queries():
    """Test parallel documentation queries using Temporal workflows."""
    client = DocumentationTemporalClient()
    
    try:
        logger.info("Starting parallel query test with 3 simultaneous workflows")
        
        # Create 3 different queries to run in parallel
        tasks = [
            client.query_documentation_async(
                query="What is liability coverage?",
                policy_category="",
            ),
            client.query_documentation_async(
                query="How do I file a claim?",
                policy_category="Home",
            ),
            client.query_documentation_async(
                query="What happens if my car is totaled?",
                policy_category="Auto",
            )
        ]
        
        # Execute all workflows in parallel
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        logger.info(f"Parallel execution completed in {end_time - start_time:.2f} seconds")
        
        # Log results for each query
        for i, result in enumerate(results):
            logger.info(f"Parallel query {i+1} found {len(result.results)} documents")
        
        return True
    except Exception as e:
        logger.error(f"Parallel query test failed: {e}", exc_info=True)
        return False
    finally:
        await client.close()


def log_result(results: List[Dict[str, Any]], test_name: str):
    """Log the results of a query."""
    logger.info(f"Test '{test_name}' found {len(results)} documents")
    
    for i, doc in enumerate(results[:3]):  # Show first 3 results
        content = doc.get("content", "")[:100]  # First 100 chars
        metadata = doc.get("document_metadata", {})
        category = metadata.get("category", "Unknown")
        
        logger.info(f"Result {i+1} - Category: {category}")
        logger.info(f"Content: {content}...")


async def main():
    """Main test function."""
    logger.info("========== TEMPORAL INTEGRATION TEST ==========")
    logger.info("This test demonstrates Temporal workflow execution for policy documentation queries")
    logger.info("You should see these workflows in the Temporal UI at http://localhost:8081")
    logger.info("==============================================")
    
    # Run sequential queries test
    logger.info("\n1. TESTING SEQUENTIAL WORKFLOW EXECUTION")
    sequential_success = await test_sequential_queries()
    
    # Run parallel queries test
    logger.info("\n2. TESTING PARALLEL WORKFLOW EXECUTION")
    parallel_success = await test_parallel_queries()
    
    if sequential_success and parallel_success:
        logger.info("\n✅ Temporal integration test completed successfully!")
        logger.info("You can now check the Temporal UI to see the executed workflows")
        logger.info("URL: http://localhost:8081")
        return 0
    else:
        logger.error("\n❌ Temporal integration test failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1) 