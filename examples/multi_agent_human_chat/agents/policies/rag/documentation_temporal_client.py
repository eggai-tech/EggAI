import uuid
from typing import List, Optional

from temporalio.client import Client

from agents.policies.rag.workflows.documentation_workflow import (
    DocumentationQueryResult,
    DocumentationQueryWorkflow,
    DocumentationQueryWorkflowInput,
)
from agents.policies.rag.workflows.ingestion_workflow import (
    DocumentData,
    DocumentIngestionResult,
    DocumentIngestionWorkflow,
    DocumentIngestionWorkflowInput,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.documentation_client")


class DocumentationTemporalClient:
    """Client for executing documentation query workflows via Temporal."""

    def __init__(
        self,
        temporal_server_url: str = "localhost:7233",
        temporal_namespace: str = "default",
        temporal_task_queue: str = "policy-rag",
    ):
        self.temporal_server_url = temporal_server_url
        self.temporal_namespace = temporal_namespace
        self.temporal_task_queue = temporal_task_queue
        self._client: Optional[Client] = None

    async def get_client(self) -> Client:
        """Get or create the Temporal client."""
        if self._client is None:
            self._client = await Client.connect(
                self.temporal_server_url, namespace=self.temporal_namespace
            )
        return self._client

    async def query_documentation_async(
        self, query: str, policy_category: str, request_id: Optional[str] = None
    ) -> DocumentationQueryResult:
        """
        Asynchronously query documentation using Temporal workflow.

        Args:
            query: The search query
            policy_category: The policy category
            request_id: Optional request identifier

        Returns:
            DocumentationQueryResult with the query results
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        logger.info(
            f"Starting async documentation query for query: '{query}', "
            f"category: '{policy_category}', request_id: '{request_id}'"
        )

        client = await self.get_client()

        workflow_input = DocumentationQueryWorkflowInput(
            query=query, policy_category=policy_category, request_id=request_id
        )

        try:
            # Execute the workflow and wait for result
            result = await client.execute_workflow(
                DocumentationQueryWorkflow.run,
                workflow_input,
                id=f"documentation-query-{request_id}",
                task_queue=self.temporal_task_queue,
            )

            logger.info(
                f"Async documentation query completed for request_id: {request_id}. "
                f"Success: {result.success}, Documents: {len(result.results)}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Async documentation query failed for request_id: {request_id}. Error: {e}",
                exc_info=True,
            )
            return DocumentationQueryResult(
                request_id=request_id,
                query=query,
                policy_category=policy_category,
                results=[],
                success=False,
                error_message=str(e),
            )

    async def ingest_documents_async(
        self,
        documents: List[DocumentData],
        force_rebuild: bool = True,
        validate_first: bool = True,
        request_id: Optional[str] = None,
    ) -> DocumentIngestionResult:
        """
        Asynchronously ingest documents and rebuild the RAG index using Temporal workflow.

        Args:
            documents: List of documents to ingest
            force_rebuild: Whether to force rebuild the index
            validate_first: Whether to validate documents before ingestion
            request_id: Optional request identifier

        Returns:
            DocumentIngestionResult with the ingestion results
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        logger.info(
            f"Starting async document ingestion for {len(documents)} documents, "
            f"force_rebuild: {force_rebuild}, validate_first: {validate_first}, "
            f"request_id: '{request_id}'"
        )

        client = await self.get_client()

        workflow_input = DocumentIngestionWorkflowInput(
            documents=documents,
            force_rebuild=force_rebuild,
            validate_first=validate_first,
            request_id=request_id,
        )

        try:
            # Execute the workflow and wait for result
            result = await client.execute_workflow(
                DocumentIngestionWorkflow.run,
                workflow_input,
                id=f"document-ingestion-{request_id}",
                task_queue=self.temporal_task_queue,
            )

            logger.info(
                f"Async document ingestion completed for request_id: {request_id}. "
                f"Success: {result.success}, Documents processed: {result.documents_processed}, "
                f"Total indexed: {result.total_documents_indexed}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Async document ingestion failed for request_id: {request_id}. Error: {e}",
                exc_info=True,
            )
            return DocumentIngestionResult(
                request_id=request_id,
                success=False,
                documents_processed=0,
                total_documents_indexed=0,
                error_message=str(e),
            )

    async def close(self):
        """Close the Temporal client connection."""
        # No need to explicitly close the client in newer Temporal SDK versions
        self._client = None
