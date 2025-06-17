import json
import os
from pathlib import Path
from typing import Any, Dict

from temporalio import activity

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.document_verification")


@activity.defn
async def verify_document_activity(
    file_path: str, 
    index_name: str = "policies_index",
    force_rebuild: bool = False
) -> Dict[str, Any]:
    """Verify if a document already exists in the search index.
    
    Args:
        file_path: Path to the document file to verify
        index_name: Name of the search index to check
        force_rebuild: Whether to skip verification and force processing
        
    Returns:
        Dict with verification results and skip recommendation
    """
    logger.info(f"Verifying document existence in index: {file_path}")
    
    try:
        if force_rebuild:
            logger.info("Force rebuild enabled, skipping verification check")
            return {
                "success": True,
                "file_exists": False,
                "should_skip": False,
                "force_rebuild": True,
            }
        
        current_dir = Path(__file__).parent.parent.parent
        index_root = current_dir / ".ragatouille"
        index_path = index_root / "colbert" / "indexes" / index_name
        docid_metadata_path = index_path / "docid_metadata_map.json"
        
        if not index_path.exists() or not docid_metadata_path.exists():
            logger.info("Index does not exist, verification passed")
            return {
                "success": True,
                "file_exists": False,
                "should_skip": False,
                "reason": "Index does not exist",
            }
        
        with open(docid_metadata_path) as f:
            metadata_map = json.load(f)
        
        filename = os.path.basename(file_path)
        
        existing_docs = [
            doc_id for doc_id, metadata in metadata_map.items()
            if metadata.get("original_file") == filename
        ]
        
        if existing_docs:
            logger.info(f"File {filename} exists with {len(existing_docs)} chunks. Recommending skip.")
            return {
                "success": True,
                "file_exists": True,
                "should_skip": True,
                "existing_chunks": len(existing_docs),
                "existing_doc_ids": existing_docs,
                "reason": f"File {filename} already exists in index",
            }
        else:
            logger.info(f"File {filename} not found in index, verification passed")
            return {
                "success": True,
                "file_exists": False,
                "should_skip": False,
                "reason": f"File {filename} not found in existing index",
            }
            
    except Exception as e:
        logger.error(f"Document verification failed: {e}", exc_info=True)
        return {
            "success": False,
            "file_exists": False,
            "should_skip": False,
            "error_message": str(e),
            "reason": "Verification failed, proceeding with processing",
        }