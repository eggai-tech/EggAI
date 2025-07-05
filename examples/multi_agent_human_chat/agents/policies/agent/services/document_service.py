from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

if TYPE_CHECKING:
    from agents.policies.agent.api.models import PolicyDocument

logger = get_console_logger("document_service")


class DocumentService:
    """Service for managing policy documents."""

    def __init__(self, vespa_client: VespaClient):
        self.vespa_client = vespa_client

    def create_policy_document(self, doc_data: dict) -> PolicyDocument:
        """Convert raw document data to PolicyDocument model.
        
        Args:
            doc_data: Raw document data from Vespa
            
        Returns:
            PolicyDocument instance
        """
        from agents.policies.agent.api.models import PolicyDocument
        
        # Generate citation
        citation = None
        if doc_data.get("page_range"):
            citation = f"{doc_data.get('source_file', 'Unknown')}, page {doc_data['page_range']}"

        return PolicyDocument(
            id=doc_data.get("id", ""),
            title=doc_data.get("title", ""),
            text=doc_data.get("text", ""),
            category=doc_data.get("category", ""),
            chunk_index=doc_data.get("chunk_index", 0),
            source_file=doc_data.get("source_file", ""),
            relevance=doc_data.get("relevance"),
            # Enhanced metadata
            page_numbers=doc_data.get("page_numbers", []),
            page_range=doc_data.get("page_range"),
            headings=doc_data.get("headings", []),
            citation=citation,
            # Relationships
            document_id=doc_data.get("document_id"),
            previous_chunk_id=doc_data.get("previous_chunk_id"),
            next_chunk_id=doc_data.get("next_chunk_id"),
            chunk_position=doc_data.get("chunk_position"),
        )

    async def list_documents(
        self,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[PolicyDocument]:
        """List all documents with optional filtering and pagination.
        
        Args:
            category: Optional category filter
            limit: Number of documents to return
            offset: Offset for pagination
            
        Returns:
            List of PolicyDocument instances
        """
        try:
            # Use an empty query to get all documents
            query = ""  # Empty query will match all documents

            # Get more results to handle pagination properly
            results = await self.vespa_client.search_documents(
                query=query,
                category=category,
                max_hits=limit + offset,  # Get enough results for pagination
            )

            # Apply pagination
            paginated_results = results[offset : offset + limit]

            # Convert to PolicyDocument models
            documents = [
                self.create_policy_document(result) 
                for result in paginated_results
            ]

            return documents

        except Exception as e:
            logger.error(f"List documents error: {e}")
            raise

    async def get_document_by_id(self, doc_id: str) -> Optional[PolicyDocument]:
        """Get a specific document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            PolicyDocument if found, None otherwise
        """
        try:
            # Try to retrieve by document ID
            result = await self.vespa_client.get_document(
                schema="policy_document", doc_id=doc_id
            )

            if result:
                return self.create_policy_document(result)

            return None

        except Exception as e:
            logger.error(f"Get document error: {e}")
            raise

    async def get_categories_stats(self) -> List[dict]:
        """Get document count statistics by category.
        
        Returns:
            List of category statistics
        """
        try:
            # Get all documents to count by category
            all_results = await self.vespa_client.search_documents(
                query="",  # Get all documents
                max_hits=1000,  # Get a reasonable number of results
            )

            # Count documents by category
            category_counts = {}
            for result in all_results:
                category = result.get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1

            # Format results
            stats = [
                {"name": category, "document_count": count}
                for category, count in sorted(category_counts.items())
            ]

            return stats

        except Exception as e:
            logger.error(f"Get categories error: {e}")
            raise

    async def clear_all_documents(self) -> dict:
        """Clear all documents from the index.
        
        Returns:
            Dictionary with deletion statistics
        """
        try:
            # Get all documents
            all_results = await self.vespa_client.search_documents(
                query="",  # Get all documents
                max_hits=10000,  # Get all results
            )

            if not all_results:
                return {
                    "total_deleted": 0,
                    "deleted_by_category": {},
                    "message": "No documents found to delete"
                }

            # Count by category before deletion
            category_counts = {}
            for result in all_results:
                category = result.get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1

            # Delete all documents
            deleted_count = 0
            async with self.vespa_client.app.http_session() as session:
                for doc in all_results:
                    doc_id = doc.get("id")
                    if doc_id:
                        response = await session.delete_data_point(
                            schema="policy_document",
                            data_id=doc_id,
                        )
                        if response.status_code == 200:
                            deleted_count += 1

            return {
                "total_deleted": deleted_count,
                "deleted_by_category": category_counts,
                "message": f"Successfully deleted {deleted_count} documents"
            }

        except Exception as e:
            logger.error(f"Clear index error: {e}")
            raise