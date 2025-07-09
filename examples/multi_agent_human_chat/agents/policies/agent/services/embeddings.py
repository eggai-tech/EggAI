import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from agents.policies.agent.config import settings
from libraries.observability.logger import get_console_logger

logger = get_console_logger("policies_agent.embeddings")

_EMBEDDING_MODEL: Optional[SentenceTransformer] = None
_EXECUTOR: Optional[ThreadPoolExecutor] = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model singleton.

    Using all-MiniLM-L6-v2 which provides good quality embeddings
    with 384 dimensions and fast inference.
    """
    global _EMBEDDING_MODEL

    if _EMBEDDING_MODEL is None:
        model_name = settings.embedding_model
        logger.info(f"Initializing embedding model: {model_name}")

        try:
            _EMBEDDING_MODEL = SentenceTransformer(model_name)
            logger.info(
                f"Embedding model initialized successfully. Dimension: {_EMBEDDING_MODEL.get_sentence_embedding_dimension()}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

    return _EMBEDDING_MODEL


def get_executor() -> ThreadPoolExecutor:
    """Get or initialize the thread pool executor for CPU-bound operations."""
    global _EXECUTOR
    
    if _EXECUTOR is None:
        # Use a small thread pool since embedding is CPU-intensive
        _EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embedding")
        logger.info("Thread pool executor initialized for embedding operations")
    
    return _EXECUTOR


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text.

    Args:
        text: Text to embed

    Returns:
        List of float values representing the embedding
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding generation")
        return []

    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []


def generate_embeddings_batch(
    texts: List[str], batch_size: int = 32
) -> List[List[float]]:
    """Generate embeddings for multiple texts in batches.

    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process at once

    Returns:
        List of embeddings, one per input text
    """
    if not texts:
        return []

    try:
        model = get_embedding_model()

        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)

        if not valid_texts:
            logger.warning("No valid texts to embed")
            return [[] for _ in texts]

        logger.info(
            f"Generating embeddings for {len(valid_texts)} texts in batches of {batch_size}"
        )
        embeddings = model.encode(
            valid_texts,
            batch_size=batch_size,
            convert_to_tensor=False,
            show_progress_bar=len(valid_texts) > 100,
        )

        result = [[] for _ in texts]
        for i, idx in enumerate(valid_indices):
            result[idx] = embeddings[i].tolist()

        return result

    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        return [[] for _ in texts]


def combine_text_for_embedding(
    text: str,
    title: Optional[str] = None,
    headings: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> str:
    """Combine multiple text fields for richer embedding.

    Args:
        text: Main text content
        title: Document title
        headings: Section headings
        category: Document category

    Returns:
        Combined text optimized for embedding
    """
    parts = []

    if category:
        parts.append(f"Category: {category}")

    if title:
        parts.append(f"Title: {title}")

    if headings:
        parts.append(f"Sections: {' > '.join(headings)}")

    parts.append(text)

    return " ".join(parts)


async def generate_embedding_async(text: str) -> List[float]:
    """Generate embedding for a single text asynchronously.
    
    Args:
        text: Text to embed
        
    Returns:
        List of float values representing the embedding
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding generation")
        return []
    
    try:
        loop = asyncio.get_event_loop()
        executor = get_executor()
        
        # Run the CPU-intensive operation in a thread pool
        embedding = await loop.run_in_executor(
            executor,
            generate_embedding,
            text
        )
        
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding asynchronously: {e}")
        return []


async def generate_embeddings_batch_async(
    texts: List[str], batch_size: int = 32
) -> List[List[float]]:
    """Generate embeddings for multiple texts asynchronously in batches.
    
    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process at once
        
    Returns:
        List of embeddings, one per input text
    """
    if not texts:
        return []
    
    try:
        loop = asyncio.get_event_loop()
        executor = get_executor()
        
        # Run the CPU-intensive operation in a thread pool
        embeddings = await loop.run_in_executor(
            executor,
            generate_embeddings_batch,
            texts,
            batch_size
        )
        
        return embeddings
    except Exception as e:
        logger.error(f"Error generating batch embeddings asynchronously: {e}")
        return [[] for _ in texts]
