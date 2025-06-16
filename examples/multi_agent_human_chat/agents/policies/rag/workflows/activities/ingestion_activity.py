import shutil
from pathlib import Path
from typing import Any, Dict, List

from ragatouille import RAGPretrainedModel
from temporalio import activity

from agents.policies.rag.indexing import get_policy_content
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.ingestion")


@activity.defn
async def document_ingestion_activity(
    documents_data: List[Dict[str, str]], force_rebuild: bool = True
) -> Dict[str, Any]:
    """
    Temporal activity for ingesting new documents and rebuilding the RAGatouille index.

    Args:
        documents_data: List of documents to ingest. Each dict should contain:
            - 'content': The document content
            - 'document_id': Unique identifier for the document
            - 'category': Document category (auto, home, health, life)
            - 'filename': Optional filename to save the document
        force_rebuild: Whether to force rebuild the index even if it exists

    Returns:
        Dict containing ingestion results and metadata
    """
    logger.info(f"Starting document ingestion for {len(documents_data)} documents")

    try:
        current_dir = Path(__file__).parent.parent.parent
        policies_dir = current_dir / "policies"
        index_root = current_dir / ".ragatouille"
        index_path = index_root / "colbert" / "indexes" / "policies_index"
        metadata_path = index_path / "metadata.json"

        # Create policies directory if it doesn't exist
        policies_dir.mkdir(exist_ok=True)

        # Check if index already exists and has metadata (idempotent check)
        if not force_rebuild and index_path.exists() and metadata_path.exists():
            logger.info(
                "Index already exists and force_rebuild=False. Checking for existing documents..."
            )

            # Check if all documents already exist as files
            all_documents_exist = True
            existing_files = []

            for doc_data in documents_data:
                if "filename" in doc_data and doc_data["filename"]:
                    file_path = policies_dir / doc_data["filename"]
                    if file_path.exists():
                        existing_files.append(str(file_path))
                    else:
                        all_documents_exist = False
                        break
                else:
                    # For documents without filenames, assume they need to be processed
                    all_documents_exist = False
                    break

            if all_documents_exist:
                logger.info(
                    f"All {len(documents_data)} documents already exist. Skipping ingestion."
                )
                return {
                    "success": True,
                    "documents_processed": 0,
                    "total_documents_indexed": len(existing_files),
                    "saved_files": existing_files,
                    "index_rebuilt": False,
                    "skipped": True,
                    "reason": "All documents already exist",
                }

        # Save new documents to files
        saved_files = []
        for doc_data in documents_data:
            if "filename" in doc_data and doc_data["filename"]:
                file_path = policies_dir / doc_data["filename"]
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(doc_data["content"])
                saved_files.append(str(file_path))
                logger.info(f"Saved document to: {file_path}")

        # Prepare for index rebuild
        if force_rebuild and index_path.exists():
            logger.info("Removing existing index for rebuild...")
            shutil.rmtree(index_path, ignore_errors=True)

        # Collect all policy documents
        policy_files = list(policies_dir.glob("*.md"))
        policies_ids = []
        my_policies_content = []
        document_metadata = []

        for policy_file in policy_files:
            policy_id = policy_file.stem
            try:
                content = get_policy_content(policy_id)
                policies_ids.append(policy_id)
                my_policies_content.append(content)

                # Determine category from filename or content
                category = (
                    policy_id
                    if policy_id in ["auto", "home", "health", "life"]
                    else "general"
                )
                document_metadata.append(
                    {
                        "category": category,
                        "type": "policy",
                        "filename": policy_file.name,
                    }
                )
                logger.info(f"Added {policy_id} to index rebuild")
            except Exception as e:
                logger.warning(f"Failed to load policy {policy_id}: {e}")

        # Add any new documents that weren't saved as files
        for doc_data in documents_data:
            if "filename" not in doc_data or not doc_data["filename"]:
                policies_ids.append(doc_data["document_id"])
                my_policies_content.append(doc_data["content"])
                document_metadata.append(
                    {
                        "category": doc_data.get("category", "general"),
                        "type": "policy",
                        "source": "ingested",
                    }
                )

        # Rebuild the index
        logger.info(f"Rebuilding index with {len(policies_ids)} documents...")

        # Create RAGPretrainedModel instance
        r = RAGPretrainedModel.from_pretrained(
            "colbert-ir/colbertv2.0", index_root=str(index_root)
        )

        # Build the index
        r.index(
            index_name="policies_index",
            collection=my_policies_content,
            document_ids=policies_ids,
            document_metadatas=document_metadata,
            use_faiss=False,
        )

        logger.info("Document ingestion and index rebuild completed successfully")

        return {
            "success": True,
            "documents_processed": len(documents_data),
            "total_documents_indexed": len(policies_ids),
            "saved_files": saved_files,
            "index_rebuilt": True,
            "index_path": str(index_path),
        }

    except Exception as e:
        logger.error(f"Document ingestion failed: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
            "documents_processed": 0,
            "index_rebuilt": False,
        }


@activity.defn
async def validate_documents_activity(
    documents_data: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Temporal activity for validating document data before ingestion.

    Args:
        documents_data: List of documents to validate

    Returns:
        Dict containing validation results
    """
    logger.info(f"Validating {len(documents_data)} documents")

    validation_errors = []
    valid_documents = []

    required_fields = ["content", "document_id"]
    valid_categories = ["auto", "home", "health", "life", "general"]

    for i, doc_data in enumerate(documents_data):
        doc_errors = []

        # Check required fields
        for field in required_fields:
            if field not in doc_data or not doc_data[field]:
                doc_errors.append(f"Missing required field: {field}")

        # Validate content length
        if "content" in doc_data and len(doc_data["content"].strip()) < 10:
            doc_errors.append("Content too short (minimum 10 characters)")

        # Validate category if provided
        if "category" in doc_data and doc_data["category"] not in valid_categories:
            doc_errors.append(f"Invalid category. Must be one of: {valid_categories}")

        # Validate document_id format
        if "document_id" in doc_data:
            doc_id = doc_data["document_id"]
            if not doc_id.replace("_", "").replace("-", "").isalnum():
                doc_errors.append(
                    "Document ID must contain only alphanumeric characters, hyphens, and underscores"
                )

        if doc_errors:
            validation_errors.append(
                {
                    "document_index": i,
                    "document_id": doc_data.get("document_id", "unknown"),
                    "errors": doc_errors,
                }
            )
        else:
            valid_documents.append(doc_data)

    is_valid = len(validation_errors) == 0

    logger.info(
        f"Validation completed. Valid: {len(valid_documents)}, Invalid: {len(validation_errors)}"
    )

    return {
        "is_valid": is_valid,
        "valid_documents": valid_documents,
        "validation_errors": validation_errors,
        "total_documents": len(documents_data),
        "valid_count": len(valid_documents),
        "invalid_count": len(validation_errors),
    }
