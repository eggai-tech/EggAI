"""Advanced evaluation tests for billing agent responses with LLM evaluators."""

import time
from datetime import datetime

import mlflow
import pytest

from agents.billing.config import settings
from agents.billing.tests.utils import (
    evaluate_response_with_llm,
    get_test_cases,
    setup_mlflow_tracking,
)
from libraries.billing_dspy.billing import billing_optimized_dspy
from libraries.billing_dspy.evaluation.metrics import precision_metric
from libraries.billing_dspy.evaluation.report import generate_test_report
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger

logger = get_console_logger("billing_agent.tests.evaluation")

# Configure language model based on settings with caching disabled for accuracy
dspy_lm = dspy_set_language_model(settings, overwrite_cache_enabled=False)


@pytest.mark.asyncio
async def test_billing_response_evaluation():
    """Test detailed evaluation of billing agent responses using LLM evaluators."""
    # Enable DSPy autologging for full trace information
    mlflow.dspy.autolog(
        log_compiles=True,
        log_traces=True,
        log_evals=True,
        log_traces_from_compile=True,
        log_traces_from_eval=True,
    )

    test_cases = get_test_cases()

    with setup_mlflow_tracking(
        "billing_agent_evaluation_tests",
        run_name=f"billing_evaluation_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
        params={
            "test_count": len(test_cases),
            "language_model": settings.language_model,
        },
    ):
        test_results = []
        evaluation_results = []

        # Process each test case
        for i, case in enumerate(test_cases):
            logger.info(f"Running evaluation for test case {i + 1}/{len(test_cases)}")

            # Get the model's response to evaluate
            start_time = time.perf_counter()
            response_generator = billing_optimized_dspy(
                chat_history=case["chat_history"]
            )

            # Extract the final response from the async generator
            agent_response = ""
            async for chunk in response_generator:
                from dspy import Prediction
                from dspy.streaming import StreamResponse

                if isinstance(chunk, StreamResponse):
                    agent_response += chunk.chunk
                elif isinstance(chunk, Prediction):
                    # Use the final response from the prediction if available
                    if hasattr(chunk, "final_response"):
                        agent_response = chunk.final_response

            response_time = (time.perf_counter() - start_time) * 1000

            # Calculate algorithmic precision
            precision_score = precision_metric(
                case["expected_response"], agent_response
            )

            # Get LLM evaluation
            evaluation_result = await evaluate_response_with_llm(
                case["chat_history"], case["expected_response"], agent_response, dspy_lm
            )
            evaluation_time = (time.perf_counter() - start_time) * 1000 - response_time

            # Log metrics
            mlflow.log_metric(f"precision_case_{i + 1}", precision_score)
            mlflow.log_metric(
                f"eval_precision_case_{i + 1}", evaluation_result.precision_score
            )
            mlflow.log_metric(f"response_time_case_{i + 1}", response_time)
            mlflow.log_metric(f"evaluation_time_case_{i + 1}", evaluation_time)

            # Record test result
            test_result = {
                "id": f"test-{i + 1}",
                "policy": case["policy_number"],
                "expected": case["expected_response"][:30] + "...",
                "response": agent_response[:30] + "..."
                if len(agent_response) > 30
                else agent_response,
                "latency": f"{response_time:.1f} ms",
                "judgment": "✔" if evaluation_result.judgment else "✘",
                "precision": f"{evaluation_result.precision_score:.2f}",
                "calc_precision": f"{precision_score:.2f}",
                "reasoning": (evaluation_result.reasoning or "")[:30] + "...",
            }
            test_results.append(test_result)

            evaluation_results.append(
                {
                    "evaluation": evaluation_result,
                    "calculated_precision": precision_score,
                }
            )

            # Log detailed evaluation for analysis
            mlflow.log_text(
                f"## Response Evaluation: Test Case {i + 1}\n\n"
                f"**Expected:** {case['expected_response']}\n\n"
                f"**Actual:** {agent_response}\n\n"
                f"**Precision Score:** {precision_score:.4f}\n\n"
                f"**LLM Judgment:** {evaluation_result.judgment}\n\n"
                f"**LLM Precision:** {evaluation_result.precision_score:.4f}\n\n"
                f"**Reasoning:**\n{evaluation_result.reasoning}",
                f"evaluation_case_{i + 1}.md",
            )

        # Calculate and log overall metrics
        if evaluation_results:
            overall_llm_precision = sum(
                e["evaluation"].precision_score for e in evaluation_results
            ) / len(evaluation_results)
            overall_calculated_precision = sum(
                e["calculated_precision"] for e in evaluation_results
            ) / len(evaluation_results)
            mlflow.log_metric("overall_llm_precision", overall_llm_precision)
            mlflow.log_metric(
                "overall_calculated_precision", overall_calculated_precision
            )

            # Generate and log report
            report = generate_test_report(test_results)
            mlflow.log_text(report, "evaluation_results.md")

            # No hard assertions here - this is for evaluation and analysis
            # This test is meant to compare different evaluation methods, not pass/fail
