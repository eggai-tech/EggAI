from datetime import timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
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


class DocumentIngestionWorkflowInput(BaseModel):
    file_path: str
    category: Optional[str] = "general"
    index_name: Optional[str] = "policies_index"
    force_rebuild: bool = False
    request_id: Optional[str] = None
    source: Optional[str] = "filesystem"  # "filesystem" or "minio"
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata for MinIO documents


class DocumentIngestionResult(BaseModel):
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
    @workflow.run
    async def run(
        self, input_data: DocumentIngestionWorkflowInput
    ) -> DocumentIngestionResult:
        # Handle both dict and object inputs for backward compatibility
        if isinstance(input_data, dict):
            input_data = DocumentIngestionWorkflowInput(**input_data)
            
        workflow.logger.info(
            f"Starting document ingestion workflow for file: {input_data.file_path}, "
            f"category: {input_data.category}, "
            f"index_name: {input_data.index_name}, "
            f"force_rebuild: {input_data.force_rebuild}, "
            f"request_id: {input_data.request_id}, "
            f"source: {input_data.source}"
        )

        # Step 1: Verify if file already exists in index
        verification_result = await workflow.execute_activity(
            verify_document_activity,
            args=[
                input_data.file_path,
                input_data.index_name,
                input_data.force_rebuild,
            ],
            start_to_close_timeout=timedelta(minutes=2),
        )

        # If file should be skipped, return early
        if verification_result.get("should_skip", False):
            workflow.logger.info(
                f"File verification indicates skip: {verification_result.get('reason')}"
            )
            return DocumentIngestionResult(
                request_id=input_data.request_id,
                success=True,
                file_path=input_data.file_path,
                documents_processed=0,
                total_documents_indexed=verification_result.get(
                    "existing_chunks", 0
                ),
                index_name=input_data.index_name,
                skipped=True,
                skip_reason=verification_result.get("reason"),
            )

        # Step 2: Load document with DocLing
        workflow.logger.info("Starting document loading")
        load_result = await workflow.execute_activity(
            load_document_activity,
            args=[input_data.file_path, input_data.source, input_data.metadata],
            start_to_close_timeout=timedelta(minutes=5),
        )

        if not load_result["success"]:
            workflow.logger.error(
                f"Document loading failed: {load_result.get('error_message')}"
            )
            raise Exception(f"Document loading failed: {load_result.get('error_message')}")

        # Step 3: Chunk document hierarchically
        workflow.logger.info("Starting document chunking")
        chunk_result = await workflow.execute_activity(
            chunk_document_activity,
            args=[load_result],
            start_to_close_timeout=timedelta(minutes=5),
        )

        if not chunk_result["success"]:
            workflow.logger.error(
                f"Document chunking failed: {chunk_result.get('error_message')}"
            )
            raise Exception(f"Document chunking failed: {chunk_result.get('error_message')}")

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
        workflow.logger.info(
            f"Starting indexing of {len(chunk_result['chunks'])} chunks"
        )
        
        # Auto-generate category from filename if using default "general" category
        # This ensures consistency with test expectations and categorization logic
        from pathlib import Path
        category = input_data.category
        if category == "general":
            category = Path(input_data.file_path).stem  # Gets "life" from "life.md"
            workflow.logger.info(f"Auto-generated category '{category}' from filename")
        
        indexing_result = await workflow.execute_activity(
            index_document_activity,
            args=[
                chunk_result["chunks"],
                input_data.file_path,
                category,  # Use auto-generated or explicit category
                input_data.index_name,
                input_data.force_rebuild,
                chunk_result.get("document_stats"),  # Pass document stats
                load_result.get("metadata"),  # Pass workflow metadata
            ],
            start_to_close_timeout=timedelta(minutes=10),
        )

        if not indexing_result["success"]:
            workflow.logger.error(
                f"Final indexing failed: {indexing_result.get('error_message')}"
            )
            raise Exception(f"Final indexing failed: {indexing_result.get('error_message')}")

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
