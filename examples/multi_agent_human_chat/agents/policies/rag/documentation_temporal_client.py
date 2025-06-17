import os
import re
import uuid
from typing import List, Optional

from temporalio.client import Client

from agents.policies.rag.workflows.ingestion_workflow import (
    DocumentIngestionResult,
    DocumentIngestionWorkflow,
    DocumentIngestionWorkflowInput,
)
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.documentation_client")


class DocumentationTemporalClient:
    """Client for executing document ingestion workflows via Temporal."""

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


    async def ingest_document_async(
        self,
        file_path: str,
        category: str = "general",
        index_name: str = "policies_index",
        force_rebuild: bool = False,
        request_id: Optional[str] = None,
    ) -> DocumentIngestionResult:
        """
        Asynchronously ingest a single document using DocLing and Temporal workflow.

        Args:
            file_path: Path to the document file
            category: Document category
            index_name: Name of the RAG index
            force_rebuild: Whether to force rebuild the index
            request_id: Optional request identifier

        Returns:
            DocumentIngestionResult with the ingestion results
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        logger.info(
            f"Starting async document ingestion for file: {file_path}, "
            f"category: {category}, index_name: {index_name}, "
            f"force_rebuild: {force_rebuild}, request_id: '{request_id}'"
        )

        client = await self.get_client()

        workflow_input = DocumentIngestionWorkflowInput(
            file_path=file_path,
            category=category,
            index_name=index_name,
            force_rebuild=force_rebuild,
            request_id=request_id,
        )

        try:
            filename = os.path.basename(file_path)
            clean_filename = re.sub(r'[^a-zA-Z0-9]', '-', os.path.splitext(filename)[0])
            clean_filename = re.sub(r'-+', '-', clean_filename).strip('-')
            
            # Execute the workflow and wait for result
            result = await client.execute_workflow(
                DocumentIngestionWorkflow.run,
                workflow_input,
                id=f"document-ingestion-{clean_filename}-{request_id}",
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
                file_path=file_path,
                documents_processed=0,
                total_documents_indexed=0,
                index_name=index_name,
                error_message=str(e),
            )


    async def close(self):
        """Close the Temporal client connection."""
        # No need to explicitly close the client in newer Temporal SDK versions
        self._client = None
