import os
from typing import Any, Dict, List

from temporalio import activity

from libraries.logger import get_console_logger
from libraries.vespa import PolicyDocument, VespaClient

logger = get_console_logger("ingestion.document_indexing")


@activity.defn
async def index_document_activity(
    chunks_data: List[Dict[str, Any]], 
    file_path: str,
    category: str = "general",
    index_name: str = "policies_index",
    force_rebuild: bool = False
) -> Dict[str, Any]:
    """Index document chunks into Vespa search index.
    
    Args:
        chunks_data: List of document chunks with text and metadata
        file_path: Original file path for metadata
        category: Document category for metadata
        index_name: Index name (preserved for compatibility)
        force_rebuild: Force rebuild flag (preserved for compatibility)
        
    Returns:
        Dict with indexing results and statistics
    """
    logger.info(f"Indexing {len(chunks_data)} chunks from {file_path} to Vespa")
    
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
        
        # Convert chunks to PolicyDocument objects
        documents = []
        for chunk_data in chunks_data:
            doc = PolicyDocument(
                id=chunk_data["id"],
                title=f"Policy Document - {os.path.basename(file_path)}",
                text=chunk_data["text"],
                category=category,
                chunk_index=chunk_data["chunk_index"],
                source_file=os.path.basename(file_path)
            )
            documents.append(doc)
        
        logger.info(f"Indexing {len(documents)} documents to Vespa")
        
        # Index documents to Vespa
        result = await vespa_client.index_documents(documents)
        
        logger.info(
            f"Vespa indexing completed: {result['successful']} successful, "
            f"{result['failed']} failed out of {result['total_documents']} total"
        )
        
        return {
            "success": result["failed"] == 0,
            "documents_processed": 1,
            "total_documents_indexed": result["successful"],
            "total_chunks": len(documents),
            "vespa_result": result,
            "errors": result.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Vespa indexing failed for {file_path}: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "documents_processed": 0,
            "total_documents_indexed": 0,
        }