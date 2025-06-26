"""Context-based metrics for retrieval evaluation."""

import math
from difflib import SequenceMatcher
from typing import List, Tuple, Optional


class ContextMetrics:
    """Calculator for context-based retrieval metrics."""

    def __init__(self, similarity_threshold: float = 0.5):
        """Initialize with configurable similarity threshold."""
        self.similarity_threshold = similarity_threshold

    def calculate_context_similarity(self, expected_context: str, chunk_text: str) -> float:
        """Calculate similarity between expected context and chunk text.
        
        Args:
            expected_context: The expected context text
            chunk_text: The retrieved chunk text
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize texts (lowercase, strip whitespace)
        expected_norm = expected_context.lower().strip()
        chunk_norm = chunk_text.lower().strip()

        # Use SequenceMatcher for similarity calculation
        matcher = SequenceMatcher(None, expected_norm, chunk_norm)
        return matcher.ratio()

    def calculate_context_coverage(self, expected_context: str, retrieved_chunks: List[dict]) -> Tuple[float, List[float]]:
        """Calculate how much of the expected context is covered by retrieved chunks.
        
        Args:
            expected_context: The expected context text
            retrieved_chunks: List of retrieved chunks
            
        Returns:
            Tuple of (best_coverage_score, list_of_chunk_similarities)
        """
        if not retrieved_chunks:
            return 0.0, []

        chunk_similarities = []
        best_coverage = 0.0

        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            similarity = self.calculate_context_similarity(expected_context, chunk_text)
            chunk_similarities.append(similarity)
            best_coverage = max(best_coverage, similarity)

        return best_coverage, chunk_similarities

    def calculate_recall_score(self, similarities: List[float]) -> float:
        """Calculate recall score - whether relevant context was found.
        
        Args:
            similarities: List of similarity scores for each chunk
            
        Returns:
            1.0 if any similarity >= threshold, 0.0 otherwise
        """
        return 1.0 if any(sim >= self.similarity_threshold for sim in similarities) else 0.0

    def calculate_precision_at_k(self, similarities: List[float], k: int = 5) -> float:
        """Calculate Precision@k score.
        
        Args:
            similarities: List of similarity scores for each chunk
            k: Number of top results to consider
            
        Returns:
            Precision@k score between 0.0 and 1.0
        """
        if not similarities:
            return 0.0

        top_k = similarities[:k]
        relevant_in_top_k = sum(1 for sim in top_k if sim >= self.similarity_threshold)
        return relevant_in_top_k / len(top_k)

    def calculate_mrr(self, similarities: List[float]) -> float:
        """Calculate Mean Reciprocal Rank.
        
        Args:
            similarities: List of similarity scores for each chunk
            
        Returns:
            MRR score between 0.0 and 1.0
        """
        for i, sim in enumerate(similarities):
            if sim >= self.similarity_threshold:
                return 1.0 / (i + 1)
        return 0.0

    def calculate_ndcg(self, similarities: List[float], k: int = 10) -> float:
        """Calculate Normalized Discounted Cumulative Gain.
        
        Args:
            similarities: List of similarity scores for each chunk
            k: Number of top results to consider
            
        Returns:
            nDCG score between 0.0 and 1.0
        """
        if not similarities:
            return 0.0

        # DCG calculation
        dcg = 0.0
        for i, sim in enumerate(similarities[:k]):
            if i == 0:
                dcg += sim
            else:
                dcg += sim / math.log2(i + 1)

        # IDCG calculation (ideal DCG with perfect ranking)
        sorted_sims = sorted(similarities[:k], reverse=True)
        idcg = 0.0
        for i, sim in enumerate(sorted_sims):
            if i == 0:
                idcg += sim
            else:
                idcg += sim / math.log2(i + 1)

        return dcg / idcg if idcg > 0 else 0.0

    def find_best_match_position(self, similarities: List[float]) -> Optional[int]:
        """Find the position (1-indexed) of the best matching chunk.
        
        Args:
            similarities: List of similarity scores for each chunk
            
        Returns:
            1-indexed position of best match, or None if no match above threshold
        """
        best_sim = 0.0
        best_pos = None

        for i, sim in enumerate(similarities):
            if sim >= self.similarity_threshold and sim > best_sim:
                best_sim = sim
                best_pos = i + 1  # 1-indexed

        return best_pos

    def calculate_all_metrics(self, expected_context: str, retrieved_chunks: List[dict]) -> dict:
        """Calculate all context-based metrics in one call.
        
        Args:
            expected_context: The expected context text
            retrieved_chunks: List of retrieved chunks
            
        Returns:
            Dictionary with all calculated metrics
        """
        context_coverage, chunk_similarities = self.calculate_context_coverage(
            expected_context, retrieved_chunks
        )

        return {
            "context_coverage": context_coverage,
            "chunk_similarities": chunk_similarities,
            "recall_score": self.calculate_recall_score(chunk_similarities),
            "precision_at_k": self.calculate_precision_at_k(chunk_similarities),
            "mrr_score": self.calculate_mrr(chunk_similarities),
            "ndcg_score": self.calculate_ndcg(chunk_similarities),
            "best_match_position": self.find_best_match_position(chunk_similarities),
        }