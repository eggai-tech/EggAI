from pathlib import Path
from typing import Any, Dict

from docling.document_converter import DocumentConverter
from temporalio import activity

from libraries.logger import get_console_logger

logger = get_console_logger("ingestion.document_loading")


@activity.defn
async def load_document_activity(file_path: str) -> Dict[str, Any]:
    """Load a document from file path using document converter.

    Args:
        file_path: Path to the document file to load

    Returns:
        Dict with success status, loaded document, and metadata
    """
    logger.info(f"Loading document: {file_path}")

    try:
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
            },
        }

    except Exception as e:
        logger.error(f"Document loading failed: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
        }
