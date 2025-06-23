"""Full document retrieval functionality for policies agent."""

import asyncio
from typing import Any, Dict, Optional

from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("policies_agent.full_document")


async def retrieve_full_document_async(
    document_id: str, 
    vespa_client: Optional[VespaClient] = None
) -> Dict[str, Any]:
    """
    Async version of retrieve_full_document.
    Retrieves all chunks for a document and reconstructs the full text.
    
    Args:
        document_id: The document identifier (e.g., "auto", "home", "life", "health")
        vespa_client: Optional VespaClient instance, creates new one if not provided
        
    Returns:
        Dict containing the full document text and metadata
    """
    logger.info(f"Retrieving full document for ID: {document_id}")
    
    try:
        # Get or create Vespa client
        if vespa_client is None:
            vespa_client = VespaClient()
        
        # Search for all chunks of this document
        chunks = await vespa_client.search_documents(
            query=f'document_id:"{document_id}"',
            category=None,
            max_hits=100  # Reasonable limit for chunks
        )
        
        if not chunks:
            logger.warning(f"No chunks found for document_id: {document_id}")
            return {
                "error": f"Document with ID '{document_id}' not found",
                "document_id": document_id
            }
        
        # Sort chunks by chunk_index
        chunks.sort(key=lambda x: x.get('chunk_index', 0))
        
        # Reconstruct the full text
        full_text = "\n\n".join(chunk.get('text', '') for chunk in chunks)
        
        # Collect metadata
        total_chunks = len(chunks)
        total_chars = sum(chunk.get('char_count', len(chunk.get('text', ''))) for chunk in chunks)
        
        # Get document-level metadata from first chunk
        first_chunk = chunks[0]
        title = first_chunk.get('title', f"Document {document_id}")
        source_file = first_chunk.get('source_file', '')
        category = first_chunk.get('category', '')
        
        # Collect all unique page numbers
        all_page_numbers = []
        for chunk in chunks:
            page_nums = chunk.get('page_numbers', [])
            all_page_numbers.extend(page_nums)
        
        # Remove duplicates and sort
        unique_pages = sorted(list(set(all_page_numbers)))
        
        # Create page range string
        page_range = None
        if unique_pages:
            if len(unique_pages) == 1:
                page_range = f"p. {unique_pages[0]}"
            else:
                page_range = f"pp. {unique_pages[0]}-{unique_pages[-1]}"
        
        # Collect all headings in order
        all_headings = []
        seen_headings = set()
        for chunk in chunks:
            headings = chunk.get('headings', [])
            for heading in headings:
                if heading not in seen_headings:
                    seen_headings.add(heading)
                    all_headings.append(heading)
        
        logger.info(f"Successfully retrieved document {document_id}: {total_chunks} chunks, {total_chars} characters")
        
        return {
            "document_id": document_id,
            "full_text": full_text,
            "total_chunks": total_chunks,
            "chunks": chunks,  # Include individual chunks for reference
            "metadata": {
                "title": title,
                "source_file": source_file,
                "category": category,
                "page_numbers": unique_pages,
                "page_range": page_range,
                "all_headings": all_headings,
                "first_chunk_id": chunks[0].get('id'),
                "last_chunk_id": chunks[-1].get('id')
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving full document: {e}")
        return {
            "error": f"Failed to retrieve document: {str(e)}",
            "document_id": document_id
        }


def retrieve_full_document(
    document_id: str, 
    vespa_client: Optional[VespaClient] = None
) -> Dict[str, Any]:
    """Retrieve and reconstruct a full document from all its chunks.
    
    Args:
        document_id: The document ID (e.g., "auto", "home", "life", "health")
        vespa_client: Optional VespaClient instance, creates new one if not provided
        
    Returns:
        Dict containing the full document text and metadata
    """
    logger.info(f"Retrieving full document for ID: {document_id}")
    
    try:
        # Get or create Vespa client
        if vespa_client is None:
            vespa_client = VespaClient()
        
        # Build YQL query to get all chunks for this document
        yql = f'select * from policy_document where document_id contains "{document_id}" order by chunk_index'
        
        # Run async search in sync context with proper query
        try:
            asyncio.get_running_loop()
            # We're in an async context, use thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Create a wrapper function that runs the async query properly
                def run_query():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(
                            vespa_client.search_documents(
                                query=f'document_id:"{document_id}"',
                                category=None,
                                max_hits=100  # Reasonable limit for chunks
                            )
                        )
                    finally:
                        loop.close()
                
                future = executor.submit(run_query)
                chunks = future.result()
        except RuntimeError:
            # No running loop, we're in sync context
            chunks = asyncio.run(
                vespa_client.search_documents(
                    query=f'document_id:"{document_id}"',
                    category=None,
                    max_hits=100  # Reasonable limit for chunks
                )
            )
        
        if not chunks:
            logger.warning(f"No chunks found for document_id: {document_id}")
            return {
                "error": f"Document with ID '{document_id}' not found",
                "document_id": document_id
            }
        
        # Sort chunks by chunk_index to ensure correct order
        chunks = sorted(chunks, key=lambda x: x.get('chunk_index', 0))
        
        # Reconstruct the full document text
        full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks])
        
        # Collect all unique headings across chunks
        all_headings = []
        seen_headings = set()
        for chunk in chunks:
            for heading in chunk.get('headings', []):
                if heading not in seen_headings:
                    all_headings.append(heading)
                    seen_headings.add(heading)
        
        # Get metadata from chunks
        first_chunk = chunks[0]
        last_chunk = chunks[-1]
        
        # Calculate total character and token counts
        total_chars = sum(chunk.get('char_count', 0) for chunk in chunks)
        total_tokens = sum(chunk.get('token_count', 0) for chunk in chunks)
        
        # Extract page range if available
        all_page_numbers = set()
        for chunk in chunks:
            all_page_numbers.update(chunk.get('page_numbers', []))
        
        page_range = None
        if all_page_numbers:
            min_page = min(all_page_numbers)
            max_page = max(all_page_numbers)
            page_range = f"{min_page}-{max_page}" if min_page != max_page else str(min_page)
        
        result = {
            "document_id": document_id,
            "category": first_chunk.get('category', 'unknown'),
            "source_file": first_chunk.get('source_file', 'unknown'),
            "full_text": full_text,
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "total_tokens": total_tokens,
            "headings": all_headings,
            "page_numbers": sorted(list(all_page_numbers)),
            "page_range": page_range,
            "chunk_ids": [chunk.get('id') for chunk in chunks],
            "metadata": {
                "first_chunk_id": first_chunk.get('id'),
                "last_chunk_id": last_chunk.get('id'),
                "title": first_chunk.get('title', 'Policy Document')
            }
        }
        
        logger.info(
            f"Successfully retrieved document {document_id}: "
            f"{len(chunks)} chunks, {total_chars} characters"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving full document {document_id}: {e}", exc_info=True)
        return {
            "error": f"Failed to retrieve document: {str(e)}",
            "document_id": document_id
        }


def get_document_chunk_range(
    document_id: str,
    start_chunk: int,
    end_chunk: Optional[int] = None,
    vespa_client: Optional[VespaClient] = None
) -> Dict[str, Any]:
    """Retrieve a specific range of chunks from a document.
    
    Useful for getting context around a specific chunk.
    
    Args:
        document_id: The document ID
        start_chunk: Starting chunk index (0-based)
        end_chunk: Ending chunk index (inclusive), None for just one chunk
        vespa_client: Optional VespaClient instance
        
    Returns:
        Dict containing the chunk range text and metadata
    """
    logger.info(f"Retrieving chunks {start_chunk}-{end_chunk} for document {document_id}")
    
    try:
        if vespa_client is None:
            vespa_client = VespaClient()
        
        # Get all chunks for the document
        full_doc = retrieve_full_document(document_id, vespa_client)
        
        if "error" in full_doc:
            return full_doc
        
        # Filter to requested range
        chunk_ids = full_doc['chunk_ids']
        if end_chunk is None:
            end_chunk = start_chunk
        
        # Validate range
        if start_chunk >= len(chunk_ids) or end_chunk >= len(chunk_ids):
            return {
                "error": f"Invalid chunk range. Document has {len(chunk_ids)} chunks (0-{len(chunk_ids)-1})",
                "document_id": document_id
            }
        
        # Get the specific chunks
        selected_chunk_ids = chunk_ids[start_chunk:end_chunk+1]
        
        # Retrieve the specific chunks
        chunks = []
        for chunk_id in selected_chunk_ids:
            try:
                results = asyncio.run(
                    vespa_client.search_documents(
                        query=f'id:"{chunk_id}"',
                        max_hits=1
                    )
                )
                if results:
                    chunks.append(results[0])
            except Exception as e:
                logger.error(f"Error retrieving chunk {chunk_id}: {e}")
        
        if not chunks:
            return {
                "error": "Failed to retrieve requested chunks",
                "document_id": document_id
            }
        
        # Combine chunk texts
        combined_text = "\n\n".join([chunk.get('text', '') for chunk in chunks])
        
        return {
            "document_id": document_id,
            "chunk_range": f"{start_chunk}-{end_chunk}",
            "text": combined_text,
            "chunks": chunks,
            "total_chunks_in_range": len(chunks)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving chunk range: {e}", exc_info=True)
        return {
            "error": f"Failed to retrieve chunk range: {str(e)}",
            "document_id": document_id
        }