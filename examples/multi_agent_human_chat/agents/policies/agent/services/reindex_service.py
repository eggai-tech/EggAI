from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

if TYPE_CHECKING:
    from agents.policies.agent.api.models import ReindexRequest, ReindexResponse
    from agents.policies.ingestion.temporal_client import TemporalClient

logger = get_console_logger("reindex_service")


class ReindexService:
    """Service for reindexing policy documents."""

    def __init__(self, vespa_client: VespaClient):
        self.vespa_client = vespa_client
        # Get base path for documents
        self.base_path = Path(__file__).parent.parent.parent / "ingestion" / "documents"

    async def clear_existing_documents(self) -> int:
        """Clear all existing documents from Vespa.
        
        Returns:
            Number of documents cleared
        """
        try:
            # Get count of existing documents first
            existing_results = await self.vespa_client.search_documents(
                query="",
                max_hits=10000,  # Get all documents
            )
            documents_to_clear = len(existing_results)

            if documents_to_clear == 0:
                return 0

            # Clear the index by deleting all documents
            deleted_count = 0
            async with self.vespa_client.app.http_session() as session:
                for doc in existing_results:
                    try:
                        response = await session.delete_data_point(
                            schema="policy_document", data_id=doc["id"]
                        )
                        if response.status_code == 200:
                            deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete document {doc['id']}: {e}")

            logger.info(f"Cleared {deleted_count} documents from Vespa")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear existing documents: {e}")
            raise

    async def get_indexing_status(self) -> dict:
        """Get current indexing status and statistics.
        
        Returns:
            Dictionary with indexing statistics
        """
        try:
            # Get all documents to analyze
            all_results = await self.vespa_client.search_documents(
                query="",  # Get all documents
                max_hits=10000,  # Get all results
            )

            # Analyze documents by category
            category_stats = {}
            document_stats = {}
            total_chunks = len(all_results)

            for result in all_results:
                category = result.get("category", "unknown")
                doc_id = result.get("document_id", "unknown")

                # Update category stats
                if category not in category_stats:
                    category_stats[category] = {"chunks": 0, "documents": set()}
                category_stats[category]["chunks"] += 1
                category_stats[category]["documents"].add(doc_id)

                # Update document stats
                if doc_id not in document_stats:
                    document_stats[doc_id] = {
                        "chunks": 0,
                        "category": category,
                        "source_file": result.get("source_file", "unknown"),
                    }
                document_stats[doc_id]["chunks"] += 1

            # Format results
            formatted_categories = {}
            for category, stats in category_stats.items():
                formatted_categories[category] = {
                    "total_chunks": stats["chunks"],
                    "total_documents": len(stats["documents"]),
                }

            formatted_documents = []
            for doc_id, stats in document_stats.items():
                formatted_documents.append({
                    "document_id": doc_id,
                    "category": stats["category"],
                    "source_file": stats["source_file"],
                    "chunk_count": stats["chunks"],
                })

            return {
                "is_indexed": total_chunks > 0,
                "total_chunks": total_chunks,
                "total_documents": len(document_stats),
                "categories": formatted_categories,
                "documents": sorted(
                    formatted_documents, key=lambda x: (x["category"], x["document_id"])
                ),
                "status": "indexed" if total_chunks > 0 else "empty",
            }

        except Exception as e:
            logger.error(f"Get indexing status error: {e}")
            raise

    def _get_document_configs(self, policy_ids: Optional[List[str]] = None) -> List[dict]:
        """Get document configurations to reindex.
        
        Args:
            policy_ids: Optional list of policy IDs to filter
            
        Returns:
            List of document configurations
        """
        # Define document configurations
        all_configs = [
            {"file": "auto.md", "category": "auto"},
            {"file": "home.md", "category": "home"},
            {"file": "life.md", "category": "life"},
            {"file": "health.md", "category": "health"},
        ]
        
        # Filter by policy IDs if specified
        if policy_ids:
            return [
                config
                for config in all_configs
                if config["category"] in policy_ids
            ]
        
        return all_configs
    
    async def _queue_document_for_ingestion(
        self, 
        temporal_client: TemporalClient,
        config: dict,
        force_rebuild: bool
    ) -> tuple[bool, str, Optional[str]]:
        """Queue a single document for ingestion.
        
        Args:
            temporal_client: Temporal client instance
            config: Document configuration
            force_rebuild: Whether to force rebuild
            
        Returns:
            Tuple of (success, policy_id, error_message)
        """
        file_path = self.base_path / config["file"]
        
        if not file_path.exists():
            error_msg = f"Document not found: {file_path}"
            logger.warning(error_msg)
            return False, config["category"], error_msg
        
        try:
            # Start ingestion workflow
            result = await temporal_client.ingest_document_async(
                file_path=str(file_path),
                category=config["category"],
                index_name="policies_index",
                force_rebuild=force_rebuild,
            )
            
            if result.success:
                logger.info(
                    f"Queued {config['category']} policy for ingestion, "
                    f"workflow_id: {result.workflow_id}"
                )
                return True, config["category"], None
            else:
                error_msg = f"Failed to queue {config['category']}: {result.error_message}"
                logger.error(error_msg)
                return False, config["category"], error_msg
                
        except Exception as e:
            error_msg = f"Error queuing {config['category']}: {str(e)}"
            logger.error(error_msg)
            return False, config["category"], error_msg
    
    def _create_reindex_response(
        self, documents_queued: int, queued_policy_ids: List[str], errors: List[str]
    ) -> ReindexResponse:
        """Create appropriate ReindexResponse based on operation results.
        
        Args:
            documents_queued: Number of documents successfully queued
            queued_policy_ids: List of policy IDs that were queued
            errors: List of error messages encountered
            
        Returns:
            ReindexResponse with appropriate status
        """
        from agents.policies.agent.api.models import ReindexResponse
        
        if documents_queued == 0 and errors:
            return ReindexResponse(
                status="failed",
                workflow_id="none",
                total_documents_submitted=0,
                policy_ids=[],
            )
        elif errors:
            return ReindexResponse(
                status="partial",
                workflow_id="multiple",
                total_documents_submitted=documents_queued,
                policy_ids=queued_policy_ids,
            )
        else:
            return ReindexResponse(
                status="success",
                workflow_id="multiple",
                total_documents_submitted=documents_queued,
                policy_ids=queued_policy_ids,
            )

    async def reindex_documents(self, request: ReindexRequest) -> ReindexResponse:
        """Reindex policy documents.
        
        Args:
            request: Reindexing request parameters
            
        Returns:
            ReindexResponse with operation results
        """
        from agents.policies.agent.api.models import ReindexResponse
        
        errors = []
        documents_cleared = 0

        try:
            # Step 1: Clear existing documents if requested
            if request.force_rebuild:
                try:
                    documents_cleared = await self.clear_existing_documents()
                except Exception as e:
                    error_msg = f"Failed to clear existing documents: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Step 2: Queue documents for re-ingestion
            from agents.policies.ingestion.temporal_client import TemporalClient
            temporal_client = TemporalClient()
            document_configs = self._get_document_configs(request.policy_ids)
            
            # Queue each document for ingestion
            documents_queued = 0
            queued_policy_ids = []

            for config in document_configs:
                success, policy_id, error_msg = await self._queue_document_for_ingestion(
                    temporal_client, config, request.force_rebuild
                )
                
                if success:
                    documents_queued += 1
                    queued_policy_ids.append(policy_id)
                elif error_msg:
                    errors.append(error_msg)

            # Prepare response based on results
            return self._create_reindex_response(
                documents_queued, queued_policy_ids, errors
            )

        except Exception as e:
            logger.error(f"Reindex operation failed: {e}")
            return ReindexResponse(
                status="failed",
                workflow_id="none",
                total_documents_submitted=0,
                policy_ids=[],
            )