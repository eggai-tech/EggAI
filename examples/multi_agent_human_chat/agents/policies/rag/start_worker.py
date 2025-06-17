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

from agents.policies.rag.documentation_temporal_client import (
    DocumentationTemporalClient,
)
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
        epilog=__doc__,
    )

    parser.add_argument(
        "--server-url",
        default="localhost:7233",
        help="Temporal server URL (default: localhost:7233)",
    )

    parser.add_argument(
        "--namespace", default="default", help="Temporal namespace (default: default)"
    )

    parser.add_argument(
        "--task-queue",
        default="policy-rag",
        help="Temporal task queue name (default: policy-rag)",
    )

    return parser.parse_args()


async def trigger_initial_document_ingestion(
    settings: PolicyDocumentationWorkerSettings,
):
    """Trigger initial document ingestion for all 4 policy documents using single-file approach."""
    logger.info("Starting initial document ingestion for all 4 policies...")

    # Select all 4 documents to ingest (auto, home, health, life)
    policy_ids = ["auto", "home", "health", "life"]
    
    # Policies directory path (relative to the rag module)
    import os
    from pathlib import Path
    current_dir = Path(__file__).parent
    policies_dir = current_dir / "policies"

    try:
        # Create client with same settings as worker
        client = DocumentationTemporalClient(
            temporal_server_url=settings.temporal_server_url,
            temporal_namespace=settings.temporal_namespace,
            temporal_task_queue=settings.temporal_task_queue,
        )

        # Process each policy file individually
        total_processed = 0
        total_indexed = 0
        
        for policy_id in policy_ids:
            policy_file = policies_dir / f"{policy_id}.md"
            
            if not policy_file.exists():
                logger.warning(f"Policy file not found: {policy_file}")
                continue
                
            logger.info(f"Processing policy file: {policy_file}")
            
            # Trigger single-file ingestion workflow
            result = await client.ingest_document_async(
                file_path=str(policy_file),
                category=policy_id,
                index_name="policies_index",
                force_rebuild=False,  # Make it idempotent
            )

            if result.success:
                if result.skipped:
                    logger.info(f"Policy {policy_id} skipped: {result.skip_reason}")
                else:
                    logger.info(f"Policy {policy_id} ingested successfully!")
                    logger.info(f"  Chunks indexed: {result.total_documents_indexed}")
                    
                total_processed += result.documents_processed
                total_indexed += result.total_documents_indexed
            else:
                logger.error(f"Policy {policy_id} ingestion failed: {result.error_message}")

        logger.info("Initial document ingestion completed!")
        logger.info(f"Total files processed: {total_processed}")
        logger.info(f"Total chunks indexed: {total_indexed}")

        await client.close()

    except Exception as e:
        logger.error(f"Error during initial document ingestion: {e}", exc_info=True)


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

    # Create shutdown event
    shutdown_event = asyncio.Event()

    # Set up async signal handlers for graceful shutdown
    def signal_handler(signum):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    # Register signal handlers using asyncio loop
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    worker = None
    try:
        # Start the worker
        worker = await run_policy_documentation_worker(settings=settings)

        logger.info("Policy Documentation worker is running. Press Ctrl+C to stop.")

        # Trigger initial document ingestion for all 4 policies
        await trigger_initial_document_ingestion(settings)

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by user")
    except Exception as e:
        logger.error(f"Error running Policy Documentation worker: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if worker:
            logger.info("Shutting down worker...")
            try:
                await worker.shutdown()
            except Exception as e:
                logger.error(f"Error during worker shutdown: {e}")
        logger.info("Policy Documentation worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
