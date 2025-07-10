import logging
from typing import Dict, List

from temporalio import activity

from agents.policies.ingestion.minio_client import MinIOClient
from libraries.integrations.vespa import VespaClient

logger = logging.getLogger(__name__)


@activity.defn
async def scan_minio_inbox_activity() -> List[Dict]:
    async with MinIOClient() as client:
        files = await client.list_inbox_files()
        logger.info(f"Found {len(files)} files in MinIO inbox")
        return files


@activity.defn
async def check_document_exists_activity(document_id: str) -> bool:
    # First check MinIO processed folder
    async with MinIOClient() as client:
        if await client.file_exists_in_processed(document_id):
            logger.info(f"Document {document_id} found in MinIO processed folder")
            return True
            
    # Then check Vespa
    vespa_client = VespaClient()
    
    try:
        # Search for document by document_id
        existing_docs = await vespa_client.search_documents(
            query=f'document_id:"{document_id}"',
            max_hits=1
        )
        
        exists = len(existing_docs) > 0
        if exists:
            logger.info(f"Document {document_id} found in Vespa")
        return exists
        
    except Exception as e:
        logger.error(f"Error checking document existence: {e}")
        # If we can't check, assume it doesn't exist to avoid data loss
        return False


@activity.defn
async def move_to_processed_activity(source_key: str) -> str:
    async with MinIOClient() as client:
        dest_key = await client.move_file(source_key, "processed")
        logger.info(f"Moved {source_key} to {dest_key}")
        return dest_key


@activity.defn
async def move_to_failed_activity(source_key: str, error: str) -> str:
    async with MinIOClient() as client:
        dest_key = await client.move_file(source_key, "failed")
        await client.add_error_metadata(dest_key, error)
        logger.info(f"Moved {source_key} to failed folder with error: {error}")
        return dest_key


@activity.defn
async def download_from_minio_activity(key: str) -> Dict:
    async with MinIOClient() as client:
        content, metadata = await client.download_file(key)
        
        return {
            "content": content,
            "metadata": metadata,
            "key": key,
            "filename": metadata.get('original_filename', key.split('/')[-1])
        }


@activity.defn
async def initialize_minio_buckets_activity() -> bool:
    try:
        async with MinIOClient() as client:
            await client.initialize_buckets()
            logger.info("MinIO buckets initialized successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to initialize MinIO buckets: {e}")
        return False