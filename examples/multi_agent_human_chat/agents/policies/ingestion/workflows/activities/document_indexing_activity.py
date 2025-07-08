import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from temporalio import activity

from agents.policies.agent.services.embeddings import (
    combine_text_for_embedding,
    generate_embeddings_batch,
)
from libraries.integrations.vespa import DocumentMetadata, PolicyDocument, VespaClient
from libraries.observability.logger import get_console_logger

logger = get_console_logger("ingestion.document_indexing")


@activity.defn
async def index_document_activity(
    chunks_data: List[Dict[str, Any]],
    file_path: str,
    category: str,
    index_name: str,
    force_rebuild: bool,
    document_stats: Optional[Dict[str, Any]],
    workflow_metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Enhanced document indexing with metadata preservation.

    Args:
        chunks_data: List of document chunks with enhanced metadata
        file_path: Original file path for metadata
        category: Document category for metadata
        index_name: Index name (preserved for compatibility)
        force_rebuild: Force rebuild flag (preserved for compatibility)
        document_stats: Document-level statistics from chunking
        workflow_metadata: Additional metadata from workflow

    Returns:
        Dict with indexing results and statistics
    """
    logger.info(
        f"Starting enhanced indexing for {len(chunks_data)} chunks from {file_path}"
    )

    try:
        if not chunks_data:
            logger.warning("No chunks provided for indexing")
            return {
                "success": True,
                "documents_processed": 1,
                "total_documents_indexed": 0,
                "skipped": True,
                "reason": "No chunks to index",
            }

        # Create Vespa client
        vespa_client = VespaClient()

        # Get document ID from first chunk or generate one
        document_id = chunks_data[0].get(
            "document_id", os.path.splitext(os.path.basename(file_path))[0]
        )

        # Prepare texts for batch embedding generation
        texts_for_embedding = []
        for chunk_data in chunks_data:
            # Combine text with metadata for richer embeddings
            combined_text = combine_text_for_embedding(
                text=chunk_data["text"],
                title=f"Policy Document - {os.path.basename(file_path)}",
                headings=chunk_data.get("headings", []),
                category=category,
            )
            texts_for_embedding.append(combined_text)

        # Generate embeddings for all chunks in batch
        logger.info(f"Generating embeddings for {len(texts_for_embedding)} chunks")
        embeddings = generate_embeddings_batch(texts_for_embedding)

        # Convert chunks to enhanced PolicyDocument objects
        documents = []
        for i, chunk_data in enumerate(chunks_data):
            doc = PolicyDocument(
                # Core fields
                id=chunk_data["id"],
                title=f"Policy Document - {os.path.basename(file_path)}",
                text=chunk_data["text"],
                category=category,
                chunk_index=chunk_data["chunk_index"],
                source_file=os.path.basename(file_path),
                # Enhanced metadata fields
                page_numbers=chunk_data.get("page_numbers", []),
                page_range=chunk_data.get("page_range"),
                headings=chunk_data.get("headings", []),
                char_count=chunk_data.get("char_count", len(chunk_data["text"])),
                token_count=chunk_data.get("token_count", 0),
                # Relationship fields
                document_id=document_id,
                previous_chunk_id=chunk_data.get("previous_chunk_id"),
                next_chunk_id=chunk_data.get("next_chunk_id"),
                chunk_position=chunk_data.get("chunk_position", 0.0),
                # Additional context
                section_path=chunk_data.get("section_path", []),
                # Vector embedding
                embedding=embeddings[i] if i < len(embeddings) else None,
            )
            documents.append(doc)

        logger.info(f"Indexing {len(documents)} enhanced documents to Vespa")

        # Index documents to Vespa
        result = await vespa_client.index_documents(documents)

        # Create and index document-level metadata if we have stats
        doc_metadata_indexed = False
        if document_stats:
            try:
                # Get file stats
                file_stats = os.stat(file_path) if os.path.exists(file_path) else None

                doc_metadata = DocumentMetadata(
                    id=document_id,
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    category=category,
                    total_pages=document_stats.get("total_pages", 0),
                    total_chunks=len(chunks_data),
                    total_characters=document_stats.get("total_characters", 0),
                    total_tokens=document_stats.get("total_tokens", 0),
                    document_type=os.path.splitext(file_path)[1]
                    .lower()
                    .replace(".", ""),
                    file_size=file_stats.st_size if file_stats else 0,
                    created_at=datetime.utcnow(),
                    last_modified=datetime.fromtimestamp(file_stats.st_mtime)
                    if file_stats
                    else None,
                    # Convert outline strings to dictionaries if needed
                    outline=[
                        {"heading": heading, "level": idx + 1}
                        for idx, heading in enumerate(document_stats.get("outline", []))
                        if isinstance(heading, str)
                    ]
                    if document_stats.get("outline")
                    else [],
                    key_sections=[],  # Could be enhanced with section detection
                )

                # For now, log the document metadata (would need separate index in production)
                logger.info(
                    f"Document metadata created: {doc_metadata.id} with {doc_metadata.total_pages} pages"
                )
                doc_metadata_indexed = True

            except Exception as e:
                logger.warning(f"Failed to create document metadata: {e}")

        logger.info(
            f"Vespa indexing completed: {result['successful']} successful, "
            f"{result['failed']} failed out of {result['total_documents']} total"
        )

        # Log sample of indexed metadata for verification
        if documents and documents[0].page_numbers:
            logger.info(
                f"Sample metadata - First chunk pages: {documents[0].page_numbers}, "
                f"headings: {documents[0].headings[:2] if documents[0].headings else 'None'}"
            )

        return {
            "success": result["failed"] == 0,
            "documents_processed": 1,
            "total_documents_indexed": result["successful"],
            "total_chunks": len(documents),
            "document_metadata_indexed": doc_metadata_indexed,
            "vespa_result": result,
            "errors": result.get("errors", []),
            "metadata_summary": {
                "pages_covered": document_stats.get("page_numbers", [])
                if document_stats
                else [],
                "total_pages": document_stats.get("total_pages", 0)
                if document_stats
                else 0,
                "has_outline": bool(document_stats.get("outline"))
                if document_stats
                else False,
            },
        }

    except Exception as e:
        logger.error(f"Enhanced indexing failed for {file_path}: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "documents_processed": 0,
            "total_documents_indexed": 0,
        }
