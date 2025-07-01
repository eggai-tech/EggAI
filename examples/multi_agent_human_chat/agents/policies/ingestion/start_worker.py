import asyncio
import signal
import sys

from agents.policies.ingestion.config import settings
from agents.policies.ingestion.documentation_temporal_client import (
    DocumentationTemporalClient,
)
from agents.policies.vespa.deploy_schema import deploy_to_vespa
from agents.policies.ingestion.workflows.worker import (
    run_policy_documentation_worker,
)
from libraries.logger import get_console_logger
from libraries.tracing import init_telemetry

logger = get_console_logger("ingestion.start_worker")


async def trigger_initial_document_ingestion():
    """Trigger initial document ingestion for all 4 policy documents using single-file approach."""
    logger.info("Starting initial document ingestion for all 4 policies...")

    # Select all 4 documents to ingest (auto, home, health, life)
    policy_ids = ["auto", "home", "health", "life"]

    # Documents directory path (relative to the ingestion module)
    from pathlib import Path

    current_dir = Path(__file__).parent
    documents_dir = current_dir / "documents"

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
            policy_file = documents_dir / f"{policy_id}.md"

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
                logger.error(
                    f"Policy {policy_id} ingestion failed: {result.error_message}"
                )

        logger.info("Initial document ingestion completed!")
        logger.info(f"Total files processed: {total_processed}")
        logger.info(f"Total chunks indexed: {total_indexed}")

        await client.close()

    except Exception as e:
        logger.error(f"Error during initial document ingestion: {e}", exc_info=True)


async def main():
    """Main function to start the worker."""
    # Initialize telemetry
    init_telemetry(app_name=settings.app_name, endpoint=settings.otel_endpoint)

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
        worker = await run_policy_documentation_worker()

        logger.info("Policy Documentation worker is running. Press Ctrl+C to stop.")

        # Deploy Vespa schema before document ingestion
        logger.info("Ensuring Vespa schema is deployed...")

        # Try to deploy with force=True to handle schema updates
        schema_deployed = deploy_to_vespa(
            config_server_url=settings.vespa_config_url,
            query_url=settings.vespa_query_url,
            force=True,
        )

        if not schema_deployed:
            logger.error(
                "Vespa schema deployment failed - cannot proceed with document ingestion"
            )
            logger.error("Please check Vespa container status and try again")
            raise Exception("Vespa schema deployment failed")

        logger.info("Vespa schema ready - proceeding with document ingestion")
        # Trigger initial document ingestion for all 4 policies
        await trigger_initial_document_ingestion()

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
