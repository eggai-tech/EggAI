import os
from pathlib import Path
from typing import Any, Dict

from temporalio import activity

from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("ingestion.document_verification")


@activity.defn
async def verify_document_activity(
    file_path: str, index_name: str = "policies_index", force_rebuild: bool = False
) -> Dict[str, Any]:
    """Verify if a document already exists in Vespa search index.

    Args:
        file_path: Path to the document file to verify
        index_name: Index name (preserved for compatibility)
        force_rebuild: Whether to skip verification and force processing

    Returns:
        Dict with verification results and skip recommendation
    """
    logger.info(f"Verifying document existence in Vespa: {file_path}")

    try:
        if force_rebuild:
            logger.info("Force rebuild enabled, skipping verification check")
            return {
                "success": True,
                "file_exists": False,
                "should_skip": False,
                "force_rebuild": True,
                "reason": "Force rebuild enabled",
            }

        # Get document ID from file path
        filename = os.path.basename(file_path)
        document_id = Path(file_path).stem

        # Create Vespa client
        vespa_client = VespaClient()

        # Search for documents with this source file
        try:
            existing_docs = await vespa_client.search_documents(
                query=f"source_file:{filename}",
                max_hits=400,  # Get all documents for this file (Vespa limit)
            )

            if existing_docs:
                logger.info(
                    f"File {filename} exists with {len(existing_docs)} chunks in Vespa. Recommending skip."
                )
                return {
                    "success": True,
                    "file_exists": True,
                    "should_skip": True,
                    "existing_chunks": len(existing_docs),
                    "existing_doc_ids": [doc["id"] for doc in existing_docs],
                    "reason": f"File {filename} already exists in Vespa index",
                }
            else:
                logger.info(f"File {filename} not found in Vespa, verification passed")
                return {
                    "success": True,
                    "file_exists": False,
                    "should_skip": False,
                    "reason": f"File {filename} not found in Vespa index",
                }

        except Exception as search_error:
            logger.warning(f"Vespa search failed during verification: {search_error}")
            # If search fails, proceed with processing to be safe
            return {
                "success": True,
                "file_exists": False,
                "should_skip": False,
                "reason": f"Vespa search failed, proceeding with processing: {search_error}",
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
