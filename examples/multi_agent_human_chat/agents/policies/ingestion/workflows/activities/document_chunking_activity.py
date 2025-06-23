from typing import Any, Dict, List, Optional, Set

from docling.chunking import HierarchicalChunker
from docling_core.types import DoclingDocument
from temporalio import activity
from transformers import GPT2TokenizerFast

from libraries.logger import get_console_logger

logger = get_console_logger("ingestion.document_chunking")


def extract_page_numbers(chunk: Any) -> List[int]:
    """Extract page numbers from chunk metadata."""
    page_numbers = set()
    
    try:
        if hasattr(chunk, "meta") and chunk.meta:
            if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                for item in chunk.meta.doc_items:
                    if hasattr(item, "prov") and item.prov:
                        for prov in item.prov:
                            if hasattr(prov, "page_no") and prov.page_no is not None:
                                page_numbers.add(int(prov.page_no))
    except Exception as e:
        logger.warning(f"Error extracting page numbers: {e}")
    
    return sorted(list(page_numbers))


def extract_headings(chunk: Any) -> List[str]:
    """Extract section headings from chunk text by parsing markdown."""
    headings = []
    
    try:
        # First try to get from metadata
        if hasattr(chunk, "meta") and chunk.meta:
            if hasattr(chunk.meta, "headings") and chunk.meta.headings:
                headings = [str(h) for h in chunk.meta.headings if h]
        
        # If no headings from metadata, parse markdown from text
        if not headings and hasattr(chunk, "text") and chunk.text:
            lines = chunk.text.split('\n')
            for line in lines:
                line = line.strip()
                # Match markdown headings (### or #### or #####)
                if line.startswith('#'):
                    # Count the number of # symbols
                    heading_level = 0
                    for char in line:
                        if char == '#':
                            heading_level += 1
                        else:
                            break
                    
                    # Extract the heading text (remove # symbols and ** formatting)
                    heading_text = line[heading_level:].strip()
                    heading_text = heading_text.replace('**', '').strip()
                    
                    if heading_text and heading_text not in headings:
                        headings.append(heading_text)
                        # Only keep the first few headings to avoid too many
                        if len(headings) >= 3:
                            break
    except Exception as e:
        logger.warning(f"Error extracting headings: {e}")
    
    return headings


def extract_section_path(chunk: Any, document: DoclingDocument) -> List[str]:
    """Extract the hierarchical section path for a chunk."""
    section_path = []
    
    try:
        # Try to get section information from chunk metadata
        if hasattr(chunk, "meta") and chunk.meta:
            # If chunk has parent references, try to build the path
            if hasattr(chunk.meta, "parent_id"):
                # This would require traversing the document structure
                # For now, we'll use headings as a proxy
                section_path = extract_headings(chunk)
    except Exception as e:
        logger.warning(f"Error extracting section path: {e}")
    
    return section_path




@activity.defn
async def chunk_document_activity(load_result: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced document chunking with metadata extraction.
    
    Args:
        load_result: Result from document loading activity containing document data
        
    Returns:
        Dict with success status, list of document chunks with metadata, and document statistics
    """
    logger.info("Starting enhanced document chunking with metadata extraction")
    
    try:
        if not load_result.get("success", False):
            return {
                "success": False,
                "error_message": f"Input loading failed: {load_result.get('error_message', 'Unknown error')}",
            }
        
        document_dict = load_result["document"]
        document = DoclingDocument.model_validate(document_dict)
        metadata = load_result.get("metadata", {})
        document_id = metadata.get("document_id", "unknown")
        
        # Initialize tokenizer for accurate token counting
        tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        
        # Configure chunker with parameters
        chunker = HierarchicalChunker(
            tokenizer="gpt2",
            max_tokens=500,
            min_tokens=100,
            merge_peers=True,
            respect_sentence_boundary=True,
            overlap_sentences=2,
        )
        
        chunks = list(chunker.chunk(document))
        total_chunks = len(chunks)
        
        # Document-level statistics
        total_characters = 0
        total_tokens = 0
        all_page_numbers: Set[int] = set()
        document_outline = []
        
        chunk_data = []
        for i, chunk in enumerate(chunks):
            if not chunk.text.strip():
                continue
            
            chunk_id = f"{document_id}_chunk_{i}"
            
            # Extract metadata
            page_numbers = extract_page_numbers(chunk)
            headings = extract_headings(chunk)
            section_path = extract_section_path(chunk, document)
            
            # Log what we found
            if headings:
                logger.info(f"Found headings for chunk {i}: {headings}")
            else:
                logger.debug(f"No headings found for chunk {i}. First 100 chars: {chunk.text[:100]}")
            
            # Calculate metrics
            char_count = len(chunk.text)
            token_count = len(tokenizer.encode(chunk.text))
            chunk_position = i / max(1, total_chunks - 1) if total_chunks > 1 else 0.0
            
            # Build page range string
            page_range = None
            if page_numbers:
                if len(page_numbers) == 1:
                    page_range = str(page_numbers[0])
                else:
                    page_range = f"{page_numbers[0]}-{page_numbers[-1]}"
            
            # Track relationships
            previous_chunk_id = f"{document_id}_chunk_{i-1}" if i > 0 else None
            next_chunk_id = f"{document_id}_chunk_{i+1}" if i < total_chunks - 1 else None
            
            # Update document statistics
            total_characters += char_count
            total_tokens += token_count
            all_page_numbers.update(page_numbers)
            
            # Add to outline if this chunk has headings
            if headings and headings not in document_outline:
                document_outline.extend(headings)
            
            chunk_data.append({
                "id": chunk_id,
                "text": chunk.text,
                "chunk_index": i,
                "page_numbers": page_numbers,
                "page_range": page_range,
                "headings": headings,
                "char_count": char_count,
                "token_count": token_count,
                "document_id": document_id,
                "previous_chunk_id": previous_chunk_id,
                "next_chunk_id": next_chunk_id,
                "chunk_position": chunk_position,
                "section_path": section_path,
            })
        
        logger.info(f"Created {len(chunk_data)} chunks with enhanced metadata")
        logger.info(f"Document spans pages: {sorted(all_page_numbers) if all_page_numbers else 'No page info'}")
        
        return {
            "success": True,
            "chunks": chunk_data,
            "total_chunks": len(chunk_data),
            "document_stats": {
                "total_pages": max(all_page_numbers) if all_page_numbers else 0,
                "total_characters": total_characters,
                "total_tokens": total_tokens,
                "page_numbers": sorted(list(all_page_numbers)),
                "outline": document_outline,
            }
        }
        
    except Exception as e:
        logger.error(f"Document chunking failed: {e}", exc_info=True)
        return {
            "success": False,
            "error_message": str(e),
        }