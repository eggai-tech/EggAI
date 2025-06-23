"""LLM evaluator for retrieval quality assessment."""

import os
import time
from typing import List

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
        log_traces=True,                    # Enable traces for normal inference
        log_traces_from_compile=False,      # Disable for compilation (too many traces)
        log_traces_from_eval=True           # Enable for evaluation
    )
    
    logger.info("Configured DSPy to use OpenAI GPT-4o-mini for evaluation with MLflow tracing")


class RetrievalQualitySignature(dspy.Signature):
    """Evaluate retrieval quality for insurance policy questions.
    
    SCORING: 0.9-1.0=Excellent, 0.7-0.8=Good, 0.5-0.6=Adequate, 0.3-0.4=Poor, 0.0-0.2=Inadequate
    JUDGMENT: Pass (True) if retrieval_quality_score >= 0.7, otherwise Fail (False)
    """
    question: str = dspy.InputField(desc="The user's question")
    expected_answer: str = dspy.InputField(desc="Expected correct answer")
    retrieved_chunks: str = dspy.InputField(desc="All retrieved document chunks as text")
    
    completeness_score: float = dspy.OutputField(desc="Completeness score (0.0-1.0)")
    relevance_score: float = dspy.OutputField(desc="Relevance score (0.0-1.0)")
    retrieval_quality_score: float = dspy.OutputField(desc="Overall quality score (0.0-1.0)")
    reasoning: str = dspy.OutputField(desc="Detailed reasoning for the scores")
    judgment: bool = dspy.OutputField(desc="Pass (True) if quality >= 0.7, else False")


class RetrievalEvaluator:
    """Evaluates retrieval quality using LLM judges."""
    
    def __init__(self):
        setup_openai_for_dspy()
        self.evaluator = dspy.asyncify(dspy.Predict(RetrievalQualitySignature))
    
    async def evaluate_single(self, retrieval_result: RetrievalResult, test_case: RetrievalTestCase) -> EvaluationResult:
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
                error=retrieval_result.error,
            )
        
        try:
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
                error=str(e),
            )
    
    def _format_chunks(self, chunks: List[dict]) -> str:
        """Format retrieved chunks for evaluation."""
        if not chunks:
            return "No chunks retrieved."
        
        return "\n\n---\n\n".join([
            f"Chunk ID: {chunk.get('id', 'unknown')}\n"
            f"Title: {chunk.get('title', 'No title')}\n"
            f"Text: {chunk.get('text', 'No text')}\n"
            f"Category: {chunk.get('category', 'unknown')}\n"
            f"Source: {chunk.get('source_file', 'unknown')}"
            for chunk in chunks
        ])