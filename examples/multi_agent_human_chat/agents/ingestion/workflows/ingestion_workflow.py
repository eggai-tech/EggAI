from datetime import timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.ingestion.workflows.activities.document_chunking_activity import (
        chunk_document_activity,
    )
    from agents.ingestion.workflows.activities.document_indexing_activity import (
        index_document_activity,
    )
    from agents.ingestion.workflows.activities.document_loading_activity import (
        load_document_activity,
    )
    from agents.ingestion.workflows.activities.document_verification_activity import (
        skip_document_already_indexed,
    )


class DocumentIngestionWorkflowInput(BaseModel):
    """Input schema for the document ingestion workflow."""

    file_path: str
    category: Optional[str] = "general"
    index_name: Optional[str] = "policies_index"
    force_rebuild: bool = False
    request_id: Optional[str] = None


class DocumentIngestionResult(BaseModel):
    """Result schema for the document ingestion workflow."""

    request_id: Optional[str]
    success: bool
    file_path: str
    documents_processed: int
    total_documents_indexed: int
    total_chunks: Optional[int] = None
    index_name: str
    index_path: Optional[str] = None
    document_metadata: Optional[Dict[str, Any]] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    error_message: Optional[str] = None


@workflow.defn
class DocumentIngestionWorkflow:
    """
    Temporal workflow for ingesting a single document.

    This workflow orchestrates the document ingestion process:
    1. Verify file doesn't already exist in index
    2. Load document using document converter
    3. Chunk document hierarchically
    4. Index chunks in search engine
    """

    @workflow.run
    async def run(
        self, input_data: DocumentIngestionWorkflowInput
    ) -> DocumentIngestionResult:
        """
        Execute the document ingestion workflow.

        Args:
            input_data: The workflow input containing file path and configuration

        Returns:
            DocumentIngestionResult with ingestion results or error information
        """
        workflow.logger.info(
            f"Starting document ingestion workflow for file: {input_data.file_path}, "
            f"category: {input_data.category}, "
            f"index_name: {input_data.index_name}, "
            f"force_rebuild: {input_data.force_rebuild}, "
            f"request_id: {input_data.request_id}"
        )

        try:
            # Step 1: Verify if file already exists in index
            verification_result = await workflow.execute_activity(
                skip_document_already_indexed,
                args=[
                    input_data.file_path,
                    input_data.force_rebuild,
                ],
                start_to_close_timeout=timedelta(minutes=2),
            )
            
            # If file should be skipped, return early
            if verification_result.get("should_skip", False):
                workflow.logger.info(f"File verification indicates skip: {verification_result.get('reason')}")
                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=True,
                    file_path=input_data.file_path,
                    documents_processed=0,
                    total_documents_indexed=verification_result.get("existing_chunks", 0),
                    index_name=input_data.index_name,
                    skipped=True,
                    skip_reason=verification_result.get("reason"),
                )
            
            # Step 2: Load document with DocLing
            workflow.logger.info("Starting document loading")
            load_result = await workflow.execute_activity(
                load_document_activity,
                args=[input_data.file_path],
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            if not load_result["success"]:
                workflow.logger.error(f"Document loading failed: {load_result.get('error_message')}")
                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=False,
                    file_path=input_data.file_path,
                    documents_processed=0,
                    total_documents_indexed=0,
                    index_name=input_data.index_name,
                    error_message=f"Document loading failed: {load_result.get('error_message')}",
                )
            
            # Step 3: Chunk document hierarchically
            workflow.logger.info("Starting document chunking")
            chunk_result = await workflow.execute_activity(
                chunk_document_activity,
                args=[load_result],
                start_to_close_timeout=timedelta(minutes=5),
            )
            
            if not chunk_result["success"]:
                workflow.logger.error(f"Document chunking failed: {chunk_result.get('error_message')}")
                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=False,
                    file_path=input_data.file_path,
                    documents_processed=0,
                    total_documents_indexed=0,
                    index_name=input_data.index_name,
                    error_message=f"Document chunking failed: {chunk_result.get('error_message')}",
                )
            
            if not chunk_result["chunks"]:
                workflow.logger.warning("No chunks generated from document")
                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=True,
                    file_path=input_data.file_path,
                    documents_processed=1,
                    total_documents_indexed=0,
                    index_name=input_data.index_name,
                    skipped=True,
                    skip_reason="No chunks generated from document",
                )
            
            # Step 4: Index chunks with Vespa
            workflow.logger.info(f"Starting indexing of {len(chunk_result['chunks'])} chunks")
            indexing_result = await workflow.execute_activity(
                index_document_activity,
                args=[
                    chunk_result["chunks"],
                    input_data.file_path,
                    input_data.category,
                ],
                start_to_close_timeout=timedelta(minutes=10),
            )
            
            if not indexing_result["success"]:
                workflow.logger.error(f"Final indexing failed: {indexing_result.get('error_message')}")
                return DocumentIngestionResult(
                    request_id=input_data.request_id,
                    success=False,
                    file_path=input_data.file_path,
                    documents_processed=0,
                    total_documents_indexed=0,
                    index_name=input_data.index_name,
                    error_message=f"Final indexing failed: {indexing_result.get('error_message')}",
                )
            
            # Success!
            workflow.logger.info(
                f"Document ingestion workflow completed successfully. "
                f"Processed {indexing_result['documents_processed']} document, "
                f"indexed {indexing_result['total_documents_indexed']} chunks"
            )
            
            return DocumentIngestionResult(
                request_id=input_data.request_id,
                success=True,
                file_path=input_data.file_path,
                documents_processed=indexing_result["documents_processed"],
                total_documents_indexed=indexing_result["total_documents_indexed"],
                total_chunks=indexing_result.get("total_chunks"),
                index_name=input_data.index_name,
                index_path=indexing_result.get("index_path"),
                document_metadata=load_result.get("metadata"),
            )

        except Exception as e:
            workflow.logger.error(f"Document ingestion workflow failed unexpectedly. Error: {str(e)}")

            return DocumentIngestionResult(
                request_id=input_data.request_id,
                success=False,
                file_path=input_data.file_path,
                documents_processed=0,
                total_documents_indexed=0,
                index_name=input_data.index_name,
                error_message=f"Workflow failed: {str(e)}",
            )
