from datetime import timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.policies.rag.workflows.activities.ingestion_activity import (
        document_ingestion_activity,
        validate_documents_activity,
    )


class DocumentData(BaseModel):
    """Schema for a single document to be ingested."""

    content: str
    document_id: str
    category: Optional[str] = "general"
    filename: Optional[str] = None


class DocumentIngestionWorkflowInput(BaseModel):
    """Input schema for the document ingestion workflow."""

    documents: List[DocumentData]
    force_rebuild: bool = True
    validate_first: bool = True
    request_id: Optional[str] = None


class DocumentIngestionResult(BaseModel):
    """Result schema for the document ingestion workflow."""

    request_id: Optional[str]
    success: bool
    documents_processed: int
    total_documents_indexed: int
    validation_results: Optional[Dict[str, Any]] = None
    ingestion_results: Optional[Dict[str, Any]] = None
    saved_files: List[str] = []
    index_rebuilt: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    error_message: Optional[str] = None


@workflow.defn
class DocumentIngestionWorkflow:
    """
    Temporal workflow for ingesting new documents and rebuilding the RAGatouille index.

    This workflow orchestrates the document ingestion process, including:
    1. Document validation (optional)
    2. Document ingestion and file saving
    3. RAGatouille index rebuilding
    4. Error handling and rollback if needed
    """

    @workflow.run
    async def run(
        self, input_data: DocumentIngestionWorkflowInput
    ) -> DocumentIngestionResult:
        """
        Execute the document ingestion workflow.

        Args:
            input_data: The workflow input containing documents and configuration

        Returns:
            DocumentIngestionResult with ingestion results or error information
        """
        workflow.logger.info(
            f"Starting document ingestion workflow for {len(input_data.documents)} documents, "
            f"force_rebuild: {input_data.force_rebuild}, "
            f"validate_first: {input_data.validate_first}, "
            f"request_id: {input_data.request_id}"
        )

        validation_results = None
        ingestion_results = None
        documents_to_process = []

        try:
            # Step 1: Document validation (if requested)
            if input_data.validate_first:
                workflow.logger.info("Starting document validation...")

                # Convert Pydantic models to dicts for the activity
                documents_data = [doc.dict() for doc in input_data.documents]

                validation_results = await workflow.execute_activity(
                    validate_documents_activity,
                    args=[documents_data],
                    start_to_close_timeout=timedelta(minutes=2),
                )

                if not validation_results["is_valid"]:
                    workflow.logger.error(
                        f"Document validation failed. "
                        f"Valid: {validation_results['valid_count']}, "
                        f"Invalid: {validation_results['invalid_count']}"
                    )

                    return DocumentIngestionResult(
                        request_id=input_data.request_id,
                        success=False,
                        documents_processed=0,
                        total_documents_indexed=0,
                        validation_results=validation_results,
                        error_message=f"Document validation failed: {validation_results['validation_errors']}",
                    )

                # Use only valid documents for processing
                documents_to_process = validation_results["valid_documents"]
                workflow.logger.info(
                    f"Document validation passed. Processing {len(documents_to_process)} valid documents"
                )
            else:
                # Use all documents without validation
                documents_to_process = [doc.dict() for doc in input_data.documents]
                workflow.logger.info("Skipping validation, processing all documents")

            # Step 2: Document ingestion and index rebuilding
            workflow.logger.info("Starting document ingestion and index rebuilding...")

            ingestion_results = await workflow.execute_activity(
                document_ingestion_activity,
                args=[documents_to_process, input_data.force_rebuild],
                start_to_close_timeout=timedelta(
                    minutes=15
                ),  # Longer timeout for index rebuilding
            )

            if not ingestion_results["success"]:
                workflow.logger.error(
                    f"Document ingestion failed: {ingestion_results.get('error_message')}"
                )

                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=False,
                    documents_processed=ingestion_results.get("documents_processed", 0),
                    total_documents_indexed=0,
                    validation_results=validation_results,
                    ingestion_results=ingestion_results,
                    error_message=ingestion_results.get("error_message"),
                )

            # Check if ingestion was skipped (idempotent case)
            if ingestion_results.get("skipped", False):
                workflow.logger.info(
                    f"Document ingestion workflow skipped: {ingestion_results.get('reason', 'Unknown reason')}. "
                    f"Total indexed: {ingestion_results['total_documents_indexed']}"
                )

                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=True,
                    documents_processed=ingestion_results["documents_processed"],
                    total_documents_indexed=ingestion_results[
                        "total_documents_indexed"
                    ],
                    validation_results=validation_results,
                    ingestion_results=ingestion_results,
                    saved_files=ingestion_results.get("saved_files", []),
                    index_rebuilt=ingestion_results.get("index_rebuilt", False),
                    skipped=True,
                    skip_reason=ingestion_results.get("reason"),
                )

            # Success!
            workflow.logger.info(
                f"Document ingestion workflow completed successfully. "
                f"Processed {ingestion_results['documents_processed']} documents, "
                f"total indexed: {ingestion_results['total_documents_indexed']}"
            )

            return DocumentIngestionResult(
                request_id=input_data.request_id,
                success=True,
                documents_processed=ingestion_results["documents_processed"],
                total_documents_indexed=ingestion_results["total_documents_indexed"],
                validation_results=validation_results,
                ingestion_results=ingestion_results,
                saved_files=ingestion_results.get("saved_files", []),
                index_rebuilt=ingestion_results.get("index_rebuilt", False),
            )

        except Exception as e:
            workflow.logger.error(
                f"Document ingestion workflow failed unexpectedly. Error: {str(e)}"
            )

            return DocumentIngestionResult(
                request_id=input_data.request_id,
                success=False,
                documents_processed=0,
                total_documents_indexed=0,
                validation_results=validation_results,
                ingestion_results=ingestion_results,
                error_message=f"Workflow failed: {str(e)}",
            )
