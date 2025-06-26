"""Main evaluator for retrieval performance assessment."""

import time
from typing import List, Optional

from libraries.logger import get_console_logger

from .context_metrics import ContextMetrics
from .llm_judge import LLMJudge
from .models import EvaluationResult, RetrievalResult, RetrievalTestCase

logger = get_console_logger("retrieval_evaluator")


class RetrievalEvaluator:
    """Evaluates retrieval quality using context similarity and optional LLM judges."""

    def __init__(
        self, enable_llm_judge: bool = True, similarity_threshold: float = 0.5
    ):
        """Initialize evaluator with configuration options.

        Args:
            enable_llm_judge: Whether to use LLM-based evaluation
            similarity_threshold: Threshold for determining relevance in context metrics
        """
        self.enable_llm_judge = enable_llm_judge
        self.context_metrics = ContextMetrics(similarity_threshold=similarity_threshold)
        self.llm_judge: Optional[LLMJudge] = None

        if self.enable_llm_judge:
            try:
                self.llm_judge = LLMJudge()
                logger.info("LLM judge enabled and configured")
            except Exception as e:
                logger.error(f"Failed to initialize LLM judge: {e}")
                self.enable_llm_judge = False
                logger.info("Falling back to context-only evaluation")
        else:
            logger.info("LLM judge disabled - using context-based metrics only")

    async def evaluate_single(
        self, retrieval_result: RetrievalResult, test_case: RetrievalTestCase
    ) -> EvaluationResult:
        """Evaluate a single retrieval result.

        Args:
            retrieval_result: The retrieval result to evaluate
            test_case: The test case with expected context

        Returns:
            EvaluationResult with all metrics
        """
        start_time = time.perf_counter()

        if retrieval_result.error:
            return self._create_error_result(retrieval_result)

        try:
            # Calculate context-based metrics
            context_metrics = self.context_metrics.calculate_all_metrics(
                test_case.expected_context, retrieval_result.retrieved_chunks
            )

            evaluation_time_ms = (time.perf_counter() - start_time) * 1000

            # Run LLM evaluation if enabled
            if self.enable_llm_judge and self.llm_judge:
                llm_results = await self._run_llm_evaluation(
                    retrieval_result, test_case
                )
                return EvaluationResult(
                    combination=retrieval_result.combination,
                    retrieval_quality_score=llm_results["retrieval_quality_score"],
                    completeness_score=llm_results["completeness_score"],
                    relevance_score=llm_results["relevance_score"],
                    reasoning=llm_results["reasoning"],
                    judgment=llm_results["judgment"],
                    evaluation_time_ms=evaluation_time_ms,
                    recall_score=context_metrics["recall_score"],
                    precision_at_k=context_metrics["precision_at_k"],
                    mrr_score=context_metrics["mrr_score"],
                    ndcg_score=context_metrics["ndcg_score"],
                    context_coverage=context_metrics["context_coverage"],
                    best_match_position=context_metrics["best_match_position"],
                )
            else:
                # LLM disabled - return result with only context metrics
                return EvaluationResult(
                    combination=retrieval_result.combination,
                    retrieval_quality_score=0.0,  # No LLM evaluation
                    completeness_score=0.0,  # No LLM evaluation
                    relevance_score=0.0,  # No LLM evaluation
                    reasoning="LLM judge disabled - context metrics only",
                    judgment=False,  # No LLM judgment
                    evaluation_time_ms=evaluation_time_ms,
                    recall_score=context_metrics["recall_score"],
                    precision_at_k=context_metrics["precision_at_k"],
                    mrr_score=context_metrics["mrr_score"],
                    ndcg_score=context_metrics["ndcg_score"],
                    context_coverage=context_metrics["context_coverage"],
                    best_match_position=context_metrics["best_match_position"],
                )

        except Exception as e:
            return self._create_exception_result(retrieval_result, start_time, e)

    async def _run_llm_evaluation(
        self, retrieval_result: RetrievalResult, test_case: RetrievalTestCase
    ) -> dict:
        """Run LLM-based evaluation.

        Args:
            retrieval_result: The retrieval result
            test_case: The test case

        Returns:
            Dictionary with LLM evaluation results
        """
        chunks_text = self._format_chunks(retrieval_result.retrieved_chunks)
        return await self.llm_judge.evaluate(
            question=test_case.question,
            expected_answer=test_case.expected_answer,
            retrieved_chunks=chunks_text,
        )

    def _format_chunks(self, chunks: List[dict]) -> str:
        """Format retrieved chunks for LLM evaluation.

        Args:
            chunks: List of retrieved chunks

        Returns:
            Formatted string representation of chunks
        """
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

    def _create_error_result(
        self, retrieval_result: RetrievalResult
    ) -> EvaluationResult:
        """Create evaluation result for retrieval errors.

        Args:
            retrieval_result: The failed retrieval result

        Returns:
            EvaluationResult with error information
        """
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

    def _create_exception_result(
        self, retrieval_result: RetrievalResult, start_time: float, exception: Exception
    ) -> EvaluationResult:
        """Create evaluation result for evaluation exceptions.

        Args:
            retrieval_result: The retrieval result
            start_time: Start time for timing calculation
            exception: The exception that occurred

        Returns:
            EvaluationResult with exception information
        """
        evaluation_time_ms = (time.perf_counter() - start_time) * 1000
        error_msg = str(exception)

        return EvaluationResult(
            combination=retrieval_result.combination,
            retrieval_quality_score=0.0,
            completeness_score=0.0,
            relevance_score=0.0,
            reasoning=f"Evaluation failed: {error_msg}",
            judgment=False,
            evaluation_time_ms=evaluation_time_ms,
            recall_score=0.0,
            precision_at_k=0.0,
            mrr_score=0.0,
            ndcg_score=0.0,
            context_coverage=0.0,
            best_match_position=None,
            error=error_msg,
        )
