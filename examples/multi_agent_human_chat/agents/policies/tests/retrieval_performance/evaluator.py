"""LLM evaluator for retrieval quality assessment."""

import math
import os
import time
from difflib import SequenceMatcher
from typing import List, Tuple

import dspy

from libraries.logger import get_console_logger

from .models import EvaluationResult, RetrievalResult, RetrievalTestCase

logger = get_console_logger("retrieval_evaluator")


def setup_openai_for_dspy():
    """Configure OpenAI for DSPy."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    # Configure DSPy first
    lm = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=lm)

    # Then enable MLflow tracing after DSPy is configured
    import mlflow

    mlflow.set_experiment("retrieval_performance_evaluation")

    # Enable autolog with explicit parameters - key insight from docs
    mlflow.dspy.autolog(
        log_traces=True,  # Enable traces for normal inference
        log_traces_from_compile=False,  # Disable for compilation (too many traces)
        log_traces_from_eval=True,  # Enable for evaluation
    )

    logger.info(
        "Configured DSPy to use OpenAI GPT-4o-mini for evaluation with MLflow tracing"
    )


class RetrievalQualitySignature(dspy.Signature):
    """Evaluate retrieval quality for insurance policy questions.

    SCORING: 0.9-1.0=Excellent, 0.7-0.8=Good, 0.5-0.6=Adequate, 0.3-0.4=Poor, 0.0-0.2=Inadequate
    JUDGMENT: Pass (True) if retrieval_quality_score >= 0.7, otherwise Fail (False)
    """

    question: str = dspy.InputField(desc="The user's question")
    expected_answer: str = dspy.InputField(desc="Expected correct answer")
    retrieved_chunks: str = dspy.InputField(
        desc="All retrieved document chunks as text"
    )

    completeness_score: float = dspy.OutputField(desc="Completeness score (0.0-1.0)")
    relevance_score: float = dspy.OutputField(desc="Relevance score (0.0-1.0)")
    retrieval_quality_score: float = dspy.OutputField(
        desc="Overall quality score (0.0-1.0)"
    )
    reasoning: str = dspy.OutputField(desc="Detailed reasoning for the scores")
    judgment: bool = dspy.OutputField(desc="Pass (True) if quality >= 0.7, else False")


class RetrievalEvaluator:
    """Evaluates retrieval quality using LLM judges."""

    def __init__(self):
        setup_openai_for_dspy()
        self.evaluator = dspy.asyncify(dspy.Predict(RetrievalQualitySignature))

    def _calculate_context_similarity(
        self, expected_context: str, chunk_text: str
    ) -> float:
        """Calculate similarity between expected context and chunk text."""
        # Normalize texts (lowercase, strip whitespace)
        expected_norm = expected_context.lower().strip()
        chunk_norm = chunk_text.lower().strip()

        # Use SequenceMatcher for similarity calculation
        matcher = SequenceMatcher(None, expected_norm, chunk_norm)
        return matcher.ratio()

    def _calculate_context_coverage(
        self, expected_context: str, retrieved_chunks: List[dict]
    ) -> Tuple[float, List[float]]:
        """Calculate how much of the expected context is covered by retrieved chunks."""
        if not retrieved_chunks:
            return 0.0, []

        chunk_similarities = []
        best_coverage = 0.0

        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            similarity = self._calculate_context_similarity(
                expected_context, chunk_text
            )
            chunk_similarities.append(similarity)
            best_coverage = max(best_coverage, similarity)

        return best_coverage, chunk_similarities

    def _calculate_recall_score(
        self, similarities: List[float], threshold: float = 0.5
    ) -> float:
        """Calculate recall score - whether relevant context was found."""
        return 1.0 if any(sim >= threshold for sim in similarities) else 0.0

    def _calculate_precision_at_k(
        self, similarities: List[float], k: int = 5, threshold: float = 0.5
    ) -> float:
        """Calculate Precision@k score."""
        if not similarities:
            return 0.0

        top_k = similarities[:k]
        relevant_in_top_k = sum(1 for sim in top_k if sim >= threshold)
        return relevant_in_top_k / len(top_k)

    def _calculate_mrr(
        self, similarities: List[float], threshold: float = 0.5
    ) -> float:
        """Calculate Mean Reciprocal Rank."""
        for i, sim in enumerate(similarities):
            if sim >= threshold:
                return 1.0 / (i + 1)
        return 0.0

    def _calculate_ndcg(self, similarities: List[float], k: int = 10) -> float:
        """Calculate Normalized Discounted Cumulative Gain."""
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

    def _find_best_match_position(
        self, similarities: List[float], threshold: float = 0.5
    ) -> int:
        """Find the position (1-indexed) of the best matching chunk."""
        best_sim = 0.0
        best_pos = None

        for i, sim in enumerate(similarities):
            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_pos = i + 1  # 1-indexed

        return best_pos

    async def evaluate_single(
        self, retrieval_result: RetrievalResult, test_case: RetrievalTestCase
    ) -> EvaluationResult:
        """Evaluate a single retrieval result."""
        start_time = time.perf_counter()

        if retrieval_result.error:
            return EvaluationResult(
                combination=retrieval_result.combination,
                retrieval_quality_score=0.0,
                completeness_score=0.0,
                relevance_score=0.0,
                reasoning=f"Skipped due to retrieval error: {retrieval_result.error}",
                judgment=False,
                evaluation_time_ms=0.0,
                recall_score=0.0,
                precision_at_k=0.0,
                mrr_score=0.0,
                ndcg_score=0.0,
                context_coverage=0.0,
                best_match_position=None,
                error=retrieval_result.error,
            )

        try:
            # Calculate context-based metrics
            context_coverage, chunk_similarities = self._calculate_context_coverage(
                test_case.expected_context, retrieval_result.retrieved_chunks
            )

            recall_score = self._calculate_recall_score(chunk_similarities)
            precision_at_k = self._calculate_precision_at_k(chunk_similarities)
            mrr_score = self._calculate_mrr(chunk_similarities)
            ndcg_score = self._calculate_ndcg(chunk_similarities)
            best_match_position = self._find_best_match_position(chunk_similarities)

            # Still run LLM evaluation for additional insights
            chunks_text = self._format_chunks(retrieval_result.retrieved_chunks)
            evaluation = await self.evaluator(
                question=test_case.question,
                expected_answer=test_case.expected_answer,
                retrieved_chunks=chunks_text,
            )

            evaluation_time_ms = (time.perf_counter() - start_time) * 1000

            return EvaluationResult(
                combination=retrieval_result.combination,
                retrieval_quality_score=evaluation.retrieval_quality_score,
                completeness_score=evaluation.completeness_score,
                relevance_score=evaluation.relevance_score,
                reasoning=evaluation.reasoning,
                judgment=evaluation.judgment,
                evaluation_time_ms=evaluation_time_ms,
                recall_score=recall_score,
                precision_at_k=precision_at_k,
                mrr_score=mrr_score,
                ndcg_score=ndcg_score,
                context_coverage=context_coverage,
                best_match_position=best_match_position,
            )

        except Exception as e:
            evaluation_time_ms = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(
                combination=retrieval_result.combination,
                retrieval_quality_score=0.0,
                completeness_score=0.0,
                relevance_score=0.0,
                reasoning=f"Evaluation failed: {str(e)}",
                judgment=False,
                evaluation_time_ms=evaluation_time_ms,
                recall_score=0.0,
                precision_at_k=0.0,
                mrr_score=0.0,
                ndcg_score=0.0,
                context_coverage=0.0,
                best_match_position=None,
                error=str(e),
            )

    def _format_chunks(self, chunks: List[dict]) -> str:
        """Format retrieved chunks for evaluation."""
        if not chunks:
            return "No chunks retrieved."

        return "\n\n---\n\n".join(
            [
                f"Position: {i + 1}\n"
                f"Title: {chunk.get('title', 'No title')}\n"
                f"Text: {chunk.get('text', 'No text')}\n"
                f"Category: {chunk.get('category', 'unknown')}\n"
                f"Source: {chunk.get('source_file', 'unknown')}"
                for i, chunk in enumerate(chunks)
            ]
        )
