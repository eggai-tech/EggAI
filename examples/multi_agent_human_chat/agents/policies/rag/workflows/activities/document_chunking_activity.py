from typing import Any, Dict, List

from docling.chunking import HierarchicalChunker
from docling_core.types import DoclingDocument
from temporalio import activity

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.document_chunking")


@activity.defn
async def chunk_document_activity(load_result: Dict[str, Any]) -> Dict[str, Any]:
    """Chunk a loaded document using hierarchical chunking.
    
    Args:
        load_result: Result from document loading activity containing document data
        
    Returns:
        Dict with success status and list of document chunks
    """
    logger.info("Chunking document with hierarchical chunker")
    
    try:
        if not load_result.get("success", False):
            return {
                "success": False,
                "error_message": f"Input loading failed: {load_result.get('error_message', 'Unknown error')}",
            }
        
        document_dict = load_result["document"]
        document = DoclingDocument.model_validate(document_dict)
        
        chunker = HierarchicalChunker(
            tokenizer="gpt2",
            max_tokens=500,
            min_tokens=100,
            merge_peers=True,
            respect_sentence_boundary=True,
            overlap_sentences=2,
        )
        
        chunks = list(chunker.chunk(document))
        
        chunk_data = []
        for i, chunk in enumerate(chunks):
            if chunk.text.strip():
                chunk_id = f"{load_result['metadata']['document_id']}_chunk_{i}"
                chunk_data.append({
                    "id": chunk_id,
                    "text": chunk.text,
                    "chunk_index": i,
                })
        
        logger.info(f"Created {len(chunk_data)} non-empty chunks")
        
        return {
            "success": True,
            "chunks": chunk_data,
            "total_chunks": len(chunk_data),
        }
        
    except Exception as e:
        logger.error(f"Document chunking failed: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
        }