import asyncio
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from agents.policies.ingestion.workflows.activities.document_chunking_activity import (
    chunk_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_indexing_activity import (
    index_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_loading_activity import (
    load_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_verification_activity import (
    verify_document_activity,
)
from agents.policies.ingestion.workflows.ingestion_workflow import (
    DocumentIngestionWorkflow,
)

logger = None


def _get_logger():
    global logger
    if logger is None:
        from libraries.logger import get_console_logger

        logger = get_console_logger("ingestion.worker")
    return logger


async def run_policy_documentation_worker(
    client: Optional[Client] = None,
) -> Worker:
    """
    Run the Policy Documentation Temporal worker.

    Args:
        client: Optional Temporal client instance

    Returns:
        The running worker instance
    """
    # Import settings here to avoid circular imports
    from agents.policies.ingestion.config import settings

    if client is None:
        client = await Client.connect(
            settings.temporal_server_url, namespace=settings.get_temporal_namespace()
        )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[DocumentIngestionWorkflow],
        activities=[
            load_document_activity,
            chunk_document_activity,
            verify_document_activity,
            index_document_activity,
        ],
    )

    _get_logger().info(
        f"Starting Policy Documentation worker on task queue: {settings.temporal_task_queue}, namespace: {settings.get_temporal_namespace()}"
    )

    asyncio.ensure_future(worker.run())
    _get_logger().info("Policy Documentation worker started successfully!")

    return worker


async def main():
    """Main function to run the worker standalone."""
    try:
        worker = await run_policy_documentation_worker()

        # Keep the worker running
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        _get_logger().info("Shutting down Policy Documentation worker...")
    except Exception as e:
        _get_logger().error(
            f"Error running Policy Documentation worker: {e}", exc_info=True
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())
