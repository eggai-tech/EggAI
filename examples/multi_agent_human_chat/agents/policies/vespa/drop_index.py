#!/usr/bin/env python3
"""
Script to drop all documents from Vespa index.

This script removes all policy documents from the Vespa search index,
effectively clearing the entire index for a fresh start.

Usage:
    python drop_index.py
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from libraries.integrations.vespa import VespaClient
from libraries.observability.logger import get_console_logger

logger = get_console_logger("drop_index")


async def get_all_document_ids(vespa_client: VespaClient) -> list[str]:
    """Get all document IDs from Vespa index."""
    logger.info("Fetching all document IDs from Vespa...")

    try:
        # Use YQL to select all documents
        async with vespa_client.vespa_app.asyncio(connections=1) as session:
            response = await session.query(
                yql=f"select * from {vespa_client.config.schema_name} where true",
                hits=400,
            )

            if response.is_successful():
                hits = response.json.get("root", {}).get("children", [])
                document_ids = [hit.get("id", "") for hit in hits if hit.get("id")]
                logger.info(f"Found {len(document_ids)} documents in index")
                return document_ids
            else:
                logger.error(f"Failed to fetch documents: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Failed to fetch document IDs: {e}")
        return []


async def delete_documents_batch(
    vespa_client: VespaClient, document_ids: list[str]
) -> dict:
    """Delete a batch of documents from Vespa using HTTP DELETE."""
    import httpx

    logger.info(f"Deleting {len(document_ids)} documents...")

    success_count = 0
    error_count = 0
    errors = []

    base_url = vespa_client.config.vespa_url

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for doc_id in document_ids:
                try:
                    # Extract the actual document ID from the full Vespa ID
                    # Format: "id:policy_document:policy_document::auto_chunk_3" -> "auto_chunk_3"
                    if "::" in doc_id:
                        actual_doc_id = doc_id.split("::")[-1]
                    else:
                        actual_doc_id = doc_id

                    # Use Document API HTTP DELETE
                    delete_url = f"{base_url}/document/v1/{vespa_client.config.schema_name}/{vespa_client.config.schema_name}/docid/{actual_doc_id}"

                    response = await client.delete(delete_url)

                    if response.status_code == 200:
                        success_count += 1
                        if success_count % 10 == 0:
                            logger.info(f"Deleted {success_count} documents...")
                    else:
                        error_count += 1
                        error_msg = f"Failed to delete {actual_doc_id}: HTTP {response.status_code}"
                        logger.warning(error_msg)
                        errors.append(error_msg)

                except Exception as e:
                    error_count += 1
                    error_msg = f"Error deleting {doc_id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

    except Exception as e:
        logger.error(f"Failed to create HTTP client: {e}")
        return {"success": False, "error": f"HTTP client creation failed: {e}"}

    return {
        "success": error_count == 0,
        "total_documents": len(document_ids),
        "deleted": success_count,
        "failed": error_count,
        "errors": errors,
    }


async def drop_index() -> bool:
    """Drop all documents from Vespa index."""
    logger.info("Starting Vespa index drop operation")

    try:
        # Create Vespa client
        vespa_client = VespaClient()

        # Check connectivity
        if not await vespa_client.check_connectivity():
            logger.error("Cannot connect to Vespa. Is it running?")
            return False

        # Get all document IDs
        document_ids = await get_all_document_ids(vespa_client)

        if not document_ids:
            logger.info("No documents found in index. Nothing to delete.")
            return True

        logger.info(f"Found {len(document_ids)} documents to delete")

        # Delete all documents
        result = await delete_documents_batch(vespa_client, document_ids)

        if result["success"]:
            logger.info(
                f"✅ Successfully deleted all {result['deleted']} documents from Vespa index"
            )
            return True
        else:
            logger.error(
                f"❌ Deletion completed with errors: {result['deleted']} deleted, {result['failed']} failed"
            )
            for error in result.get("errors", [])[:5]:  # Show first 5 errors
                logger.error(f"  - {error}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error during index drop: {e}")
        return False


def main():
    """Main entry point."""
    print("🗑️  Vespa Index Drop Tool")
    print("=" * 50)

    try:
        success = asyncio.run(drop_index())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
