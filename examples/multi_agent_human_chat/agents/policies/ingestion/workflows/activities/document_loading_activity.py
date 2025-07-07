import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict

import aiofiles
from docling.document_converter import DocumentConverter
from temporalio import activity

from agents.policies.ingestion.minio_client import MinIOClient
from libraries.logger import get_console_logger

logger = get_console_logger("ingestion.document_loading")


@activity.defn
async def load_document_activity(file_path: str, source: str = "filesystem", metadata: Dict = None) -> Dict[str, Any]:
    """Load a document from file path or MinIO using document converter.

    Args:
        file_path: Path to the document file to load (or MinIO key if source="minio")
        source: Source of the document ("filesystem" or "minio")
        metadata: Additional metadata (used for MinIO documents)

    Returns:
        Dict with success status, loaded document, and metadata
    """
    logger.info(f"Loading document: {file_path} from {source}")

    try:
        # Handle MinIO source
        if source == "minio":
            # Download from MinIO
            async with MinIOClient() as client:
                content, minio_metadata = await client.download_file(file_path)
                original_filename = minio_metadata.get('original_filename', Path(file_path).name)
            
            # Create temporary file for processing
            suffix = Path(original_filename).suffix
            
            # Create a unique temporary file path
            tmp_dir = tempfile.gettempdir()
            tmp_filename = f"doc_{uuid.uuid4().hex}{suffix}"
            tmp_file_path = os.path.join(tmp_dir, tmp_filename)
            
            # Write content asynchronously
            async with aiofiles.open(tmp_file_path, 'wb') as tmp_file:
                await tmp_file.write(content)
                
            try:
                converter = DocumentConverter()
                result = converter.convert(tmp_file_path)
                document = result.document
                
                logger.info(f"Successfully loaded MinIO document with {len(document.pages)} pages")
                
                # Use MinIO metadata for document ID
                document_id = minio_metadata.get("document_id", Path(original_filename).stem)
                
                return {
                    "success": True,
                    "document": document.model_dump(),
                    "metadata": {
                        "num_pages": len(document.pages),
                        "filename": original_filename,
                        "file_path": file_path,  # MinIO key
                        "document_id": document_id,
                        "source": "minio",
                        "sha256": minio_metadata.get("sha256"),
                        "minio_metadata": minio_metadata
                    },
                }
            finally:
                # Clean up temporary file
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                
        # Handle filesystem source (original behavior)
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        converter = DocumentConverter()
        result = converter.convert(file_path)
        document = result.document

        logger.info(f"Successfully loaded document with {len(document.pages)} pages")

        return {
            "success": True,
            "document": document.model_dump(),
            "metadata": {
                "num_pages": len(document.pages),
                "filename": file_path_obj.name,
                "file_path": str(file_path_obj),
                "document_id": file_path_obj.stem,
                "source": "filesystem"
            },
        }

    except Exception as e:
        logger.error(f"Document loading failed: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
        }
