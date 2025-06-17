import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from temporalio import activity
from ragatouille import RAGPretrainedModel

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.document_indexing")


@activity.defn
async def index_document_activity(
    chunks_data: List[Dict[str, Any]], 
    file_path: str,
    category: str = "general",
    index_name: str = "policies_index",
    force_rebuild: bool = False
) -> Dict[str, Any]:
    """Index document chunks into the search index.
    
    Args:
        chunks_data: List of document chunks with text and metadata
        file_path: Original file path for metadata
        category: Document category for metadata
        index_name: Name of the search index to update
        force_rebuild: Whether to rebuild the entire index
        
    Returns:
        Dict with indexing results and statistics
    """
    logger.info(f"Indexing {len(chunks_data)} chunks from {file_path}")
    
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
        
        current_dir = Path(__file__).parent.parent.parent
        index_root = current_dir / ".ragatouille"
        index_path = index_root / "colbert" / "indexes" / index_name
        
        documents = []
        document_ids = []
        document_metadatas = []
        
        for chunk_data in chunks_data:
            documents.append(chunk_data["text"])
            document_ids.append(chunk_data["id"])
            document_metadatas.append({
                "category": category,
                "type": "policy",
                "chunk_index": chunk_data["chunk_index"],
                "source": "document_converter",
                "original_file": os.path.basename(file_path),
            })
        
        if force_rebuild and index_path.exists():
            logger.info("Removing existing index for rebuild")
            shutil.rmtree(index_path, ignore_errors=True)
        
        logger.info(f"Indexing {len(documents)} chunks into {index_name}")
        
        rag = RAGPretrainedModel.from_pretrained(
            "colbert-ir/colbertv2.0", 
            index_root=str(index_root)
        )
        
        if index_path.exists() and not force_rebuild:
            try:
                existing_rag = RAGPretrainedModel.from_index(str(index_path))
                existing_rag.add_to_index(
                    new_collection=documents,
                    new_document_ids=document_ids,
                    new_document_metadatas=document_metadatas,
                )
                logger.info(f"Successfully added {len(documents)} chunks to existing index")
            except Exception as e:
                logger.warning(f"Failed to add to existing index, rebuilding: {e}")
                rag.index(
                    index_name=index_name,
                    collection=documents,
                    document_ids=document_ids,
                    document_metadatas=document_metadatas,
                    use_faiss=False,
                )
        else:
            rag.index(
                index_name=index_name,
                collection=documents,
                document_ids=document_ids,
                document_metadatas=document_metadatas,
                use_faiss=False,
            )
        
        logger.info(f"Successfully indexed {len(documents)} chunks from {file_path}")
        
        return {
            "success": True,
            "documents_processed": 1,
            "total_documents_indexed": len(documents),
            "total_chunks": len(documents),
            "index_name": index_name,
            "index_path": str(index_path),
        }
        
    except Exception as e:
        logger.error(f"Document indexing failed for {file_path}: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "documents_processed": 0,
            "total_documents_indexed": 0,
        }