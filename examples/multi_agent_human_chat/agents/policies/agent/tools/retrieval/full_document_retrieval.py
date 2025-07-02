"""Full document retrieval functionality for policies agent."""

from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel

from agents.policies.agent.utils import run_async_safe
from libraries.logger import get_console_logger
from libraries.vespa import VespaClient

logger = get_console_logger("policies_agent.full_document")


class DocumentChunk(BaseModel):
    """Model for a document chunk."""

    id: str
    text: str
    chunk_index: int
    char_count: Optional[int] = 0
    token_count: Optional[int] = 0
    page_numbers: List[int] = []
    headings: List[str] = []
    title: Optional[str] = None
    source_file: Optional[str] = None
    category: Optional[str] = None


class DocumentMetadata(BaseModel):
    """Model for document metadata."""

    title: str
    source_file: str
    category: str
    page_numbers: List[int]
    page_range: Optional[str]
    all_headings: List[str]
    first_chunk_id: str
    last_chunk_id: str


class FullDocument(BaseModel):
    """Model for a complete document."""

    document_id: str
    full_text: str
    total_chunks: int
    total_characters: int
    total_tokens: int
    chunks: List[Dict[str, Any]]
    metadata: DocumentMetadata
    chunk_ids: List[str]
    # Legacy fields for backward compatibility
    category: str
    source_file: str
    headings: List[str]
    page_numbers: List[int]
    page_range: Optional[str]


class DocumentError(BaseModel):
    """Model for document retrieval errors."""

    error: str
    document_id: str


class DocumentChunkRange(BaseModel):
    """Model for a range of document chunks."""

    document_id: str
    chunk_range: str
    text: str
    chunks: List[Dict[str, Any]]
    total_chunks_in_range: int


class DocumentRetrievalError(Exception):
    """Custom exception for document retrieval errors."""

    def __init__(
        self, document_id: str, message: str, original_error: Optional[Exception] = None
    ):
        self.document_id = document_id
        self.message = message
        self.original_error = original_error
        super().__init__(f"Document {document_id}: {message}")


def _get_vespa_client(vespa_client: Optional[VespaClient] = None) -> VespaClient:
    """Get or create Vespa client."""
    return vespa_client or VespaClient()


def _sort_chunks_by_index(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort chunks by their chunk_index."""
    return sorted(chunks, key=lambda x: x.get("chunk_index", 0))


def _extract_unique_page_numbers(chunks: List[Dict[str, Any]]) -> List[int]:
    """Extract unique page numbers from chunks and return sorted list."""
    all_page_numbers: Set[int] = set()
    for chunk in chunks:
        page_nums = chunk.get("page_numbers", [])
        all_page_numbers.update(page_nums)
    return sorted(list(all_page_numbers))


def _create_page_range(page_numbers: List[int]) -> Optional[str]:
    """Create page range string from page numbers."""
    if not page_numbers:
        return None

    if len(page_numbers) == 1:
        return f"p. {page_numbers[0]}"
    else:
        return f"pp. {page_numbers[0]}-{page_numbers[-1]}"


def _extract_unique_headings(chunks: List[Dict[str, Any]]) -> List[str]:
    """Extract unique headings from chunks in order."""
    all_headings = []
    seen_headings: Set[str] = set()

    for chunk in chunks:
        headings = chunk.get("headings", [])
        for heading in headings:
            if heading not in seen_headings:
                seen_headings.add(heading)
                all_headings.append(heading)

    return all_headings


def _calculate_total_stats(chunks: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Calculate total character and token counts from chunks."""
    total_chars = sum(
        chunk.get("char_count", len(chunk.get("text", ""))) for chunk in chunks
    )
    total_tokens = sum(chunk.get("token_count", 0) for chunk in chunks)
    return total_chars, total_tokens


def _create_document_metadata(chunks: List[Dict[str, Any]]) -> DocumentMetadata:
    """Create document metadata from chunks."""
    if not chunks:
        raise ValueError("Cannot create metadata from empty chunks list")

    first_chunk = chunks[0]
    last_chunk = chunks[-1]

    page_numbers = _extract_unique_page_numbers(chunks)
    page_range = _create_page_range(page_numbers)
    all_headings = _extract_unique_headings(chunks)

    return DocumentMetadata(
        title=first_chunk.get("title", "Policy Document"),
        source_file=first_chunk.get("source_file", "unknown"),
        category=first_chunk.get("category", "unknown"),
        page_numbers=page_numbers,
        page_range=page_range,
        all_headings=all_headings,
        first_chunk_id=first_chunk.get("id", ""),
        last_chunk_id=last_chunk.get("id", ""),
    )


async def _search_document_chunks(
    document_id: str, vespa_client: VespaClient
) -> List[Dict[str, Any]]:
    """Search for all chunks of a document."""
    chunks = await vespa_client.search_documents(
        query=f'document_id:"{document_id}"',
        category=None,
        max_hits=100,  # Reasonable limit for chunks
    )

    if not chunks:
        raise DocumentRetrievalError(
            document_id, f"No chunks found for document_id: {document_id}"
        )

    return _sort_chunks_by_index(chunks)


async def retrieve_full_document_async(
    document_id: str, vespa_client: Optional[VespaClient] = None
) -> Dict[str, Any]:
    """
    Retrieve and reconstruct a full document from all its chunks.

    Args:
        document_id: The document identifier (e.g., "auto", "home", "life", "health")
        vespa_client: Optional VespaClient instance, creates new one if not provided

    Returns:
        Dict containing the full document text and metadata or error information
    """
    logger.info(f"Retrieving full document for ID: {document_id}")

    try:
        client = _get_vespa_client(vespa_client)
        chunks = await _search_document_chunks(document_id, client)

        # Reconstruct the full text
        full_text = "\n\n".join(chunk.get("text", "") for chunk in chunks)

        # Calculate statistics
        total_chars, total_tokens = _calculate_total_stats(chunks)

        # Create metadata
        metadata = _create_document_metadata(chunks)

        # Create result
        chunk_ids = [chunk.get("id", "") for chunk in chunks]

        result = FullDocument(
            document_id=document_id,
            full_text=full_text,
            total_chunks=len(chunks),
            total_characters=total_chars,
            total_tokens=total_tokens,
            chunks=chunks,
            metadata=metadata,
            chunk_ids=chunk_ids,
            # Legacy fields for backward compatibility
            category=metadata.category,
            source_file=metadata.source_file,
            headings=metadata.all_headings,
            page_numbers=metadata.page_numbers,
            page_range=metadata.page_range,
        )

        logger.info(
            f"Successfully retrieved document {document_id}: {len(chunks)} chunks, {total_chars} characters"
        )

        return result.model_dump()

    except DocumentRetrievalError as e:
        logger.warning(str(e))
        return DocumentError(error=e.message, document_id=document_id).model_dump()
    except Exception as e:
        logger.error(
            f"Error retrieving full document {document_id}: {e}", exc_info=True
        )
        return DocumentError(
            error=f"Failed to retrieve document: {str(e)}", document_id=document_id
        ).model_dump()


def retrieve_full_document(
    document_id: str, vespa_client: Optional[VespaClient] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for retrieve_full_document_async.

    Args:
        document_id: The document ID (e.g., "auto", "home", "life", "health")
        vespa_client: Optional VespaClient instance, creates new one if not provided

    Returns:
        Dict containing the full document text and metadata or error information
    """
    # Use our utility to handle async/sync context
    return run_async_safe(retrieve_full_document_async(document_id, vespa_client))


def get_document_chunk_range(
    document_id: str,
    start_chunk: int,
    end_chunk: Optional[int] = None,
    vespa_client: Optional[VespaClient] = None,
) -> Dict[str, Any]:
    """
    Retrieve a specific range of chunks from a document.

    Args:
        document_id: The document ID
        start_chunk: Starting chunk index (0-based)
        end_chunk: Ending chunk index (inclusive), None for just one chunk
        vespa_client: Optional VespaClient instance

    Returns:
        Dict containing the chunk range text and metadata or error information
    """
    logger.info(
        f"Retrieving chunks {start_chunk}-{end_chunk} for document {document_id}"
    )

    try:
        client = _get_vespa_client(vespa_client)

        # Get all chunks for the document
        full_doc_result = retrieve_full_document(document_id, client)

        if "error" in full_doc_result:
            return full_doc_result

        # Validate and adjust range
        chunk_ids = (
            full_doc_result["chunk_ids"] if "chunk_ids" in full_doc_result else []
        )
        if end_chunk is None:
            end_chunk = start_chunk

        if (
            start_chunk >= len(chunk_ids)
            or end_chunk >= len(chunk_ids)
            or start_chunk < 0
        ):
            return DocumentError(
                error=f"Invalid chunk range. Document has {len(chunk_ids)} chunks (0-{len(chunk_ids) - 1})",
                document_id=document_id,
            ).model_dump()

        # Get the specific chunks using the full document's chunks
        all_chunks = full_doc_result.get("chunks", [])
        selected_chunks = all_chunks[start_chunk : end_chunk + 1]

        if not selected_chunks:
            return DocumentError(
                error="Failed to retrieve requested chunks", document_id=document_id
            ).model_dump()

        # Combine chunk texts
        combined_text = "\n\n".join(chunk.get("text", "") for chunk in selected_chunks)

        result = DocumentChunkRange(
            document_id=document_id,
            chunk_range=f"{start_chunk}-{end_chunk}",
            text=combined_text,
            chunks=selected_chunks,
            total_chunks_in_range=len(selected_chunks),
        )

        return result.model_dump()

    except Exception as e:
        logger.error(f"Error retrieving chunk range: {e}", exc_info=True)
        return DocumentError(
            error=f"Failed to retrieve chunk range: {str(e)}", document_id=document_id
        ).model_dump()
