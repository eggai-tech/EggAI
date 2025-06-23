"""Vespa client for document indexing and querying."""

from asyncio import Semaphore, gather
from typing import Any, Dict, List, Optional

import httpx
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential
from vespa.application import Vespa
from vespa.io import VespaQueryResponse

from libraries.logger import get_console_logger
from libraries.tracing import create_tracer

from .config import VespaConfig
from .schemas import PolicyDocument

logger = get_console_logger("vespa_client")
tracer = create_tracer("vespa", "client")


class VespaClient:
    """Client for interacting with Vespa search engine."""
    
    def __init__(self, config: Optional[VespaConfig] = None):
        self.config = config or VespaConfig()
        self._vespa_app: Optional[Vespa] = None
        
    @property
    def vespa_app(self) -> Vespa:
        """Get or create Vespa application connection."""
        if self._vespa_app is None:
            self._vespa_app = Vespa(url=self.config.vespa_url)
        return self._vespa_app
    
    
    @tracer.start_as_current_span("check_connectivity")
    async def check_connectivity(self) -> bool:
        """Check if Vespa is accessible."""
        try:
            async with self.vespa_app.asyncio(
                connections=1, 
                timeout=httpx.Timeout(5.0)
            ) as session:
                # Try a simple query to test connectivity
                response = await session.query(
                    yql="select * from policy_document where true limit 1"
                )
                logger.info("Vespa connectivity check successful")
                return True
        except Exception as e:
            logger.error(f"Vespa connectivity check failed: {e}")
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2))
    async def _upload_single_document(self, session, document: PolicyDocument) -> bool:
        """Upload a single document with retry logic."""
        logger.debug(f"Uploading document: {document.id}")
        
        try:
            response = await session.feed_data_point(
                data_id=document.id,
                fields=document.to_vespa_dict(),
                schema=self.config.schema_name
            )
            
            if not response.is_successful():
                logger.error(
                    f"Failed to upload document {document.id}: "
                    f"Status: {response.status_code}, Content: {response.json}"
                )
                raise Exception(f"Upload failed for document {document.id}")
            
            logger.debug(f"Successfully uploaded document {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading document {document.id}: {e}")
            raise
    
    @tracer.start_as_current_span("index_documents")
    async def index_documents(self, documents: List[PolicyDocument]) -> Dict[str, Any]:
        """Index multiple documents to Vespa."""
        logger.info(f"Starting indexing of {len(documents)} documents")
        
        # Check connectivity first
        if not await self.check_connectivity():
            raise Exception("Cannot connect to Vespa")
        
        success_count = 0
        error_count = 0
        errors = []
        
        async with self.vespa_app.asyncio(
            connections=self.config.vespa_connections,
            timeout=httpx.Timeout(self.config.vespa_timeout)
        ) as session:
            # Use semaphore to limit concurrent uploads
            semaphore = Semaphore(self.config.vespa_connections)
            
            async def upload_with_limit(doc: PolicyDocument):
                nonlocal success_count, error_count
                async with semaphore:
                    try:
                        await self._upload_single_document(session, doc)
                        success_count += 1
                    except RetryError as e:
                        error_count += 1
                        error_msg = f"Final failure for document {doc.id}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                    except Exception as e:
                        error_count += 1
                        error_msg = f"Unexpected error for document {doc.id}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            # Execute all uploads
            tasks = [upload_with_limit(doc) for doc in documents]
            await gather(*tasks, return_exceptions=True)
        
        result = {
            "total_documents": len(documents),
            "successful": success_count,
            "failed": error_count,
            "errors": errors
        }
        
        logger.info(
            f"Indexing completed: {success_count} successful, {error_count} failed"
        )
        
        return result
    
    @tracer.start_as_current_span("search_documents")
    async def search_documents(
        self,
        query: str,
        category: Optional[str] = None,
        max_hits: Optional[int] = None,
        ranking_profile: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for documents in Vespa."""
        max_hits = max_hits or self.config.max_hits
        ranking_profile = ranking_profile or self.config.ranking_profile
        
        logger.info(f"Searching for: '{query}', category: '{category}', max_hits: {max_hits}")
        
        # Build YQL query
        if query:
            yql_conditions = ["userInput(@query)"]
        else:
            # If no query provided, match all documents
            yql_conditions = ["true"]
        
        if category:
            yql_conditions.append(f'category contains "{category}"')
        
        yql = f"select * from {self.config.schema_name} where {' and '.join(yql_conditions)}"
        
        try:
            async with self.vespa_app.asyncio(
                connections=1,
                timeout=httpx.Timeout(self.config.vespa_timeout)
            ) as session:
                # Build query parameters
                query_params = {
                    "yql": yql,
                    "hits": max_hits,
                    "ranking": ranking_profile
                }
                
                # Only add query parameter if there's an actual query
                if query:
                    query_params["query"] = query
                
                response: VespaQueryResponse = await session.query(**query_params)
                
                if not response.is_successful():
                    logger.error(
                        f"Search failed: status {response.status_code}, "
                        f"response: {response.json}"
                    )
                    return []
                
                # Extract hits from response
                results = []
                root_data = response.json.get("root", {})
                children = root_data.get("children", [])
                
                for child in children:
                    fields = child.get("fields", {})
                    results.append({
                        # Core fields
                        "id": fields.get("id", ""),
                        "title": fields.get("title", ""),
                        "text": fields.get("text", ""),
                        "category": fields.get("category", ""),
                        "chunk_index": fields.get("chunk_index", 0),
                        "source_file": fields.get("source_file", ""),
                        "relevance": child.get("relevance", 0.0),
                        # Enhanced metadata fields
                        "page_numbers": fields.get("page_numbers", []),
                        "page_range": fields.get("page_range"),
                        "headings": fields.get("headings", []),
                        "char_count": fields.get("char_count", 0),
                        "token_count": fields.get("token_count", 0),
                        # Relationship fields
                        "document_id": fields.get("document_id"),
                        "previous_chunk_id": fields.get("previous_chunk_id"),
                        "next_chunk_id": fields.get("next_chunk_id"),
                        "chunk_position": fields.get("chunk_position"),
                        # Additional context
                        "section_path": fields.get("section_path", [])
                    })
                
                logger.info(f"Found {len(results)} documents")
                return results
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    @tracer.start_as_current_span("get_document_count")
    async def get_document_count(self) -> int:
        """Get total number of documents in the index."""
        try:
            async with self.vespa_app.asyncio(connections=1) as session:
                response = await session.query(
                    yql=f"select * from {self.config.schema_name} where true limit 0",
                    hits=0
                )
                
                if response.is_successful():
                    total_count = response.json.get("root", {}).get("fields", {}).get("totalCount", 0)
                    logger.info(f"Total documents in index: {total_count}")
                    return total_count
                else:
                    logger.error(f"Failed to get document count: {response.status_code}")
                    return 0
                    
        except Exception as e:
            logger.error(f"Error getting document count: {e}")
            return 0
    
    @tracer.start_as_current_span("vector_search")
    async def vector_search(
        self,
        query_embedding: List[float],
        category: Optional[str] = None,
        max_hits: Optional[int] = None,
        ranking_profile: str = "semantic"
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search using embeddings.
        
        Args:
            query_embedding: The query embedding vector
            category: Optional category filter
            max_hits: Maximum number of results
            ranking_profile: Ranking profile to use (default: semantic)
            
        Returns:
            List of matching documents with relevance scores
        """
        max_hits = max_hits or self.config.max_hits
        
        logger.info(f"Performing vector search, category: '{category}', max_hits: {max_hits}")
        
        # Build YQL query for nearest neighbor search
        yql_conditions = [f"{{targetHits: {max_hits}}}nearestNeighbor(embedding, query_embedding)"]
        
        if category:
            yql_conditions.append(f'category contains "{category}"')
        
        yql = f"select * from {self.config.schema_name} where {' and '.join(yql_conditions)}"
        
        try:
            async with self.vespa_app.asyncio(
                connections=1,
                timeout=httpx.Timeout(self.config.vespa_timeout)
            ) as session:
                # Build query parameters
                # Format embedding as tensor string for Vespa
                tensor_values = ",".join([f"{{{i}:{v}}}" for i, v in enumerate(query_embedding)])
                tensor_string = f"{{x:{tensor_values}}}"
                
                query_params = {
                    "yql": yql,
                    "hits": max_hits,
                    "ranking": ranking_profile,
                    "ranking.features.query(query_embedding)": tensor_string
                }
                
                response: VespaQueryResponse = await session.query(**query_params)
                
                if not response.is_successful():
                    logger.error(
                        f"Vector search failed: status {response.status_code}, "
                        f"response: {response.json}"
                    )
                    return []
                
                # Extract and return results
                results = self._extract_search_results(response)
                logger.info(f"Vector search found {len(results)} documents")
                return results
                
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    @tracer.start_as_current_span("hybrid_search")
    async def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        category: Optional[str] = None,
        max_hits: Optional[int] = None,
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining keyword and vector search.
        
        Args:
            query: Text query for keyword search
            query_embedding: Query embedding for vector search
            category: Optional category filter
            max_hits: Maximum number of results
            alpha: Weight for vector search (0-1, higher = more vector influence)
            
        Returns:
            List of matching documents with combined relevance scores
        """
        max_hits = max_hits or self.config.max_hits
        
        logger.info(f"Performing hybrid search: '{query}', alpha: {alpha}, category: '{category}'")
        
        # Build YQL query combining text and vector search
        yql_conditions = []
        
        if query:
            yql_conditions.append("userInput(@query)")
        
        # Add nearest neighbor for vector search
        yql_conditions.append(f"{{targetHits: {max_hits}}}nearestNeighbor(embedding, query_embedding)")
        
        if category:
            yql_conditions.append(f'category contains "{category}"')
        
        yql = f"select * from {self.config.schema_name} where {' or '.join(yql_conditions[:2])}"
        if category:
            yql = f"select * from {self.config.schema_name} where ({' or '.join(yql_conditions[:2])}) and {yql_conditions[2]}"
        
        try:
            async with self.vespa_app.asyncio(
                connections=1,
                timeout=httpx.Timeout(self.config.vespa_timeout)
            ) as session:
                # Build query parameters
                # Format embedding as tensor string for Vespa
                tensor_values = ",".join([f"{{{i}:{v}}}" for i, v in enumerate(query_embedding)])
                tensor_string = f"{{x:{tensor_values}}}"
                
                query_params = {
                    "yql": yql,
                    "hits": max_hits,
                    "ranking": "hybrid",
                    "ranking.features.query(alpha)": alpha,
                    "ranking.features.query(query_embedding)": tensor_string
                }
                
                # Only add text query if provided
                if query:
                    query_params["query"] = query
                
                response: VespaQueryResponse = await session.query(**query_params)
                
                if not response.is_successful():
                    logger.error(
                        f"Hybrid search failed: status {response.status_code}, "
                        f"response: {response.json}"
                    )
                    return []
                
                # Extract and return results
                results = self._extract_search_results(response)
                logger.info(f"Hybrid search found {len(results)} documents")
                return results
                
        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            return []
    
    def _extract_search_results(self, response: VespaQueryResponse) -> List[Dict[str, Any]]:
        """Extract search results from Vespa response."""
        results = []
        root_data = response.json.get("root", {})
        children = root_data.get("children", [])
        
        for child in children:
            fields = child.get("fields", {})
            results.append({
                # Core fields
                "id": fields.get("id", ""),
                "title": fields.get("title", ""),
                "text": fields.get("text", ""),
                "category": fields.get("category", ""),
                "chunk_index": fields.get("chunk_index", 0),
                "source_file": fields.get("source_file", ""),
                "relevance": child.get("relevance", 0.0),
                # Enhanced metadata fields
                "page_numbers": fields.get("page_numbers", []),
                "page_range": fields.get("page_range"),
                "headings": fields.get("headings", []),
                "char_count": fields.get("char_count", 0),
                "token_count": fields.get("token_count", 0),
                # Relationship fields
                "document_id": fields.get("document_id"),
                "previous_chunk_id": fields.get("previous_chunk_id"),
                "next_chunk_id": fields.get("next_chunk_id"),
                "chunk_position": fields.get("chunk_position"),
                # Additional context
                "section_path": fields.get("section_path", [])
            })
        
        return results