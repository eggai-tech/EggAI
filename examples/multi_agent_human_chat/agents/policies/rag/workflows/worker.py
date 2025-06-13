import asyncio
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from agents.policies.rag.workflows.activities.retrieval_activity import (
    policy_retrieval_activity,
)
from agents.policies.rag.workflows.documentation_workflow import (
    DocumentationQueryWorkflow,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.worker")


class PolicyDocumentationWorkerSettings:
    """Settings for the Policy Documentation Temporal worker."""
    
    def __init__(self):
        self.temporal_server_url: str = "localhost:7233"
        self.temporal_namespace: str = "default"
        self.temporal_task_queue: str = "policy-rag"


async def run_policy_documentation_worker(
    client: Optional[Client] = None,
    settings: Optional[PolicyDocumentationWorkerSettings] = None
) -> Worker:
    """
    Run the Policy Documentation Temporal worker.
    
    Args:
        client: Optional Temporal client instance
        settings: Optional worker settings
        
    Returns:
        The running worker instance
    """
    if settings is None:
        settings = PolicyDocumentationWorkerSettings()
    
    if client is None:
        client = await Client.connect(
            settings.temporal_server_url,
            namespace=settings.temporal_namespace
        )
    
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[DocumentationQueryWorkflow],
        activities=[policy_retrieval_activity],
    )
    
    logger.info(f"Starting Policy Documentation worker on task queue: {settings.temporal_task_queue}")
    
    # Start the worker
    asyncio.ensure_future(worker.run())
    logger.info("Policy Documentation worker started successfully!")
    
    return worker


async def main():
    """Main function to run the worker standalone."""
    try:
        worker = await run_policy_documentation_worker()
        
        # Keep the worker running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Shutting down Policy Documentation worker...")
    except Exception as e:
        logger.error(f"Error running Policy Documentation worker: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())