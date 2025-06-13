#!/usr/bin/env python3
"""
Standalone script to start the Policy RAG Temporal worker.

Usage:
    python start_worker.py [--server-url TEMPORAL_SERVER_URL] [--namespace NAMESPACE] [--task-queue TASK_QUEUE]

Example:
    python start_worker.py --server-url localhost:7233 --namespace default --task-queue policy-rag
"""

import argparse
import asyncio
import signal
import sys

from agents.policies.rag.workflows.worker import (
    PolicyDocumentationWorkerSettings,
    run_policy_documentation_worker,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.start_worker")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Start the Policy RAG Temporal worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--server-url",
        default="localhost:7233",
        help="Temporal server URL (default: localhost:7233)"
    )
    
    parser.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default)"
    )
    
    parser.add_argument(
        "--task-queue",
        default="policy-rag",
        help="Temporal task queue name (default: policy-rag)"
    )
    
    return parser.parse_args()


async def main():
    """Main function to start the worker."""
    args = parse_args()
    
    # Create worker settings
    settings = PolicyDocumentationWorkerSettings()
    settings.temporal_server_url = args.server_url
    settings.temporal_namespace = args.namespace
    settings.temporal_task_queue = args.task_queue
    
    logger.info("Starting Policy Documentation Temporal worker with settings:")
    logger.info(f"  Server URL: {settings.temporal_server_url}")
    logger.info(f"  Namespace: {settings.temporal_namespace}")
    logger.info(f"  Task Queue: {settings.temporal_task_queue}")
    
    try:
        # Start the worker
        worker = await run_policy_documentation_worker(settings=settings)
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Policy Documentation worker is running. Press Ctrl+C to stop.")
        
        # Keep the worker running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by user")
    except Exception as e:
        logger.error(f"Error running Policy Documentation worker: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Policy Documentation worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)