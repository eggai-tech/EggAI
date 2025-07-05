import os

import dspy

from libraries.logger import get_console_logger

logger = get_console_logger("llm_judge")


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


class LLMJudge:
    """LLM-based evaluator for retrieval quality assessment."""

    def __init__(self):
        """Initialize LLM judge with OpenAI configuration."""
        self._setup_openai()
        self.evaluator = dspy.asyncify(dspy.Predict(RetrievalQualitySignature))

    def _setup_openai(self):
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

        # Enable autolog with explicit parameters
        mlflow.dspy.autolog(
            log_traces=True,  # Enable traces for normal inference
            log_traces_from_compile=False,  # Disable for compilation (too many traces)
            log_traces_from_eval=True,  # Enable for evaluation
        )

        logger.info(
            "Configured DSPy to use OpenAI GPT-4o-mini for evaluation with MLflow tracing"
        )

    async def evaluate(
        self, question: str, expected_answer: str, retrieved_chunks: str
    ) -> dict:
        """Evaluate retrieval quality using LLM judge.

        Args:
            question: The user's question
            expected_answer: Expected correct answer
            retrieved_chunks: Formatted retrieved chunks text

        Returns:
            Dictionary with evaluation results
        """
        try:
            evaluation = await self.evaluator(
                question=question,
                expected_answer=expected_answer,
                retrieved_chunks=retrieved_chunks,
            )

            return {
                "retrieval_quality_score": evaluation.retrieval_quality_score,
                "completeness_score": evaluation.completeness_score,
                "relevance_score": evaluation.relevance_score,
                "reasoning": evaluation.reasoning,
                "judgment": evaluation.judgment,
            }
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            return {
                "retrieval_quality_score": 0.0,
                "completeness_score": 0.0,
                "relevance_score": 0.0,
                "reasoning": f"LLM evaluation failed: {str(e)}",
                "judgment": False,
            }
