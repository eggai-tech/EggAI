"""
Retrieval Performance Test Suite

Staged testing: Query -> Evaluate -> Report
Results logged to MLflow for tracking and analysis.
"""

import asyncio
import unittest
from datetime import datetime
from typing import List, Tuple

import pytest

from agents.policies.tests.retrieval_performance.api_client import RetrievalAPIClient
from agents.policies.tests.retrieval_performance.data_utilities import (
    get_retrieval_test_cases,
)
from agents.policies.tests.retrieval_performance.evaluator import RetrievalEvaluator
from agents.policies.tests.retrieval_performance.mlflow_reporter import MLflowReporter
from agents.policies.tests.retrieval_performance.models import (
    EvaluationResult,
    ParameterCombination,
    RetrievalResult,
    RetrievalTestConfiguration,
)
from libraries.logger import get_console_logger

logger = get_console_logger("retrieval_performance_test")


class RetrievalPerformanceTester:
    """Orchestrates staged retrieval performance testing."""

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        config: RetrievalTestConfiguration = None,
    ):
        self.base_url = base_url
        self.config = config or RetrievalTestConfiguration()
        self.test_cases = get_retrieval_test_cases()
        self.combinations = self._generate_combinations()

        self.api_client = RetrievalAPIClient(base_url)
        self.evaluator = RetrievalEvaluator()
        self.reporter = MLflowReporter()

        logger.info(f"Generated {len(self.combinations)} parameter combinations")

    def _generate_combinations(self) -> List[ParameterCombination]:
        """Generate all parameter combinations to test."""
        combinations = []
        for test_case in self.test_cases:
            for search_type in self.config.search_types:
                for max_hits in self.config.max_hits_values:
                    combinations.append(
                        ParameterCombination(
                            test_case_id=test_case.id,
                            search_type=search_type,
                            max_hits=max_hits,
                        )
                    )
        return combinations

    async def stage1_query_all(self) -> List[RetrievalResult]:
        """Stage 1: Execute all retrieval queries."""
        logger.info(
            f"Stage 1: Starting retrieval for {len(self.combinations)} combinations"
        )

        if self.config.parallel_queries:
            results = await self._query_parallel()
        else:
            results = await self._query_sequential()

        successful = len([r for r in results if r.error is None])
        logger.info(
            f"Stage 1 completed: {successful}/{len(results)} queries successful"
        )
        return results

    async def _query_parallel(self) -> List[RetrievalResult]:
        """Execute queries in parallel with semaphore control."""
        semaphore = asyncio.Semaphore(self.config.max_query_workers)

        async def bounded_query(combination):
            async with semaphore:
                test_case = next(
                    (tc for tc in self.test_cases if tc.id == combination.test_case_id),
                    None,
                )
                if not test_case:
                    return RetrievalResult(
                        combination=combination,
                        retrieved_chunks=[],
                        retrieval_time_ms=0.0,
                        total_hits=0,
                        error=f"Test case {combination.test_case_id} not found",
                    )
                return await self.api_client.query_single(combination, test_case)

        results = await asyncio.gather(
            *[bounded_query(combination) for combination in self.combinations],
            return_exceptions=True,
        )

        return [
            r
            if not isinstance(r, Exception)
            else RetrievalResult(self.combinations[i], [], 0.0, 0, str(r))
            for i, r in enumerate(results)
        ]

    async def _query_sequential(self) -> List[RetrievalResult]:
        """Execute queries sequentially."""
        results = []
        for combination in self.combinations:
            test_case = next(
                (tc for tc in self.test_cases if tc.id == combination.test_case_id),
                None,
            )
            if test_case:
                result = await self.api_client.query_single(combination, test_case)
                results.append(result)
                await asyncio.sleep(0.1)
        return results

    async def stage2_evaluate_all(
        self, retrieval_results: List[RetrievalResult]
    ) -> List[EvaluationResult]:
        """Stage 2: Evaluate all retrieval results using LLM judge."""
        logger.info(
            f"Stage 2: Starting LLM evaluation for {len(retrieval_results)} results"
        )

        if self.config.parallel_evaluations:
            results = await self._evaluate_parallel(retrieval_results)
        else:
            results = await self._evaluate_sequential(retrieval_results)

        successful = len([r for r in results if r.error is None])
        logger.info(
            f"Stage 2 completed: {successful}/{len(results)} evaluations successful"
        )
        return results

    async def _evaluate_parallel(
        self, retrieval_results: List[RetrievalResult]
    ) -> List[EvaluationResult]:
        """Evaluate results in parallel with semaphore control."""
        semaphore = asyncio.Semaphore(self.config.max_eval_workers)

        async def bounded_evaluate(retrieval_result):
            async with semaphore:
                test_case = next(
                    (
                        tc
                        for tc in self.test_cases
                        if tc.id == retrieval_result.combination.test_case_id
                    ),
                    None,
                )
                if not test_case:
                    return EvaluationResult(
                        combination=retrieval_result.combination,
                        retrieval_quality_score=0.0,
                        completeness_score=0.0,
                        relevance_score=0.0,
                        reasoning="Test case not found",
                        judgment=False,
                        evaluation_time_ms=0.0,
                        error=f"Test case {retrieval_result.combination.test_case_id} not found",
                    )
                return await self.evaluator.evaluate_single(retrieval_result, test_case)

        results = await asyncio.gather(
            *[bounded_evaluate(result) for result in retrieval_results],
            return_exceptions=True,
        )

        return [
            r
            if not isinstance(r, Exception)
            else EvaluationResult(
                retrieval_results[i].combination,
                0.0,
                0.0,
                0.0,
                f"Exception: {r}",
                False,
                0.0,
                str(r),
            )
            for i, r in enumerate(results)
        ]

    async def _evaluate_sequential(
        self, retrieval_results: List[RetrievalResult]
    ) -> List[EvaluationResult]:
        """Evaluate results sequentially."""
        results = []
        for retrieval_result in retrieval_results:
            test_case = next(
                (
                    tc
                    for tc in self.test_cases
                    if tc.id == retrieval_result.combination.test_case_id
                ),
                None,
            )
            if test_case:
                evaluation = await self.evaluator.evaluate_single(
                    retrieval_result, test_case
                )
                results.append(evaluation)
                await asyncio.sleep(0.1)
        return results

    def stage3_report_to_mlflow(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult],
    ) -> None:
        """Stage 3: Report results to MLflow."""
        self.reporter.report_results(retrieval_results, evaluation_results)

    async def run_staged_evaluation(
        self,
    ) -> Tuple[List[RetrievalResult], List[EvaluationResult]]:
        """Run complete staged evaluation: Query -> Evaluate -> Report."""
        if not await self.api_client.ensure_api_running():
            raise RuntimeError(
                f"API at {self.base_url} is not available and could not be started"
            )

        logger.info("Starting staged retrieval evaluation")
        logger.info(
            f"{len(self.test_cases)} test cases, {len(self.combinations)} total combinations"
        )

        retrieval_results = await self.stage1_query_all()
        evaluation_results = await self.stage2_evaluate_all(retrieval_results)
        self.stage3_report_to_mlflow(retrieval_results, evaluation_results)

        logger.info("Staged evaluation completed successfully")
        return retrieval_results, evaluation_results

    def find_best_combination(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult],
    ) -> dict:
        """Find the best performing parameter combination."""
        combination_stats = {}

        # Group by parameter combination (search_type + max_hits)
        for eval_result in evaluation_results:
            if eval_result.error:
                continue

            combo_key = f"{eval_result.combination.search_type}_hits{eval_result.combination.max_hits}"

            if combo_key not in combination_stats:
                combination_stats[combo_key] = {
                    "search_type": eval_result.combination.search_type,
                    "max_hits": eval_result.combination.max_hits,
                    "quality_scores": [],
                    "pass_count": 0,
                    "total_count": 0,
                    "retrieval_times": [],
                }

            stats = combination_stats[combo_key]
            stats["quality_scores"].append(eval_result.retrieval_quality_score)
            stats["total_count"] += 1
            if eval_result.judgment:
                stats["pass_count"] += 1

            # Find matching retrieval time
            matching_retrieval = next(
                (
                    r
                    for r in retrieval_results
                    if (
                        r.combination.test_case_id
                        == eval_result.combination.test_case_id
                        and r.combination.search_type
                        == eval_result.combination.search_type
                        and r.combination.max_hits == eval_result.combination.max_hits
                        and r.error is None
                    )
                ),
                None,
            )
            if matching_retrieval:
                stats["retrieval_times"].append(matching_retrieval.retrieval_time_ms)

        # Calculate aggregate metrics for each combination
        for _combo_key, stats in combination_stats.items():
            stats["avg_quality"] = sum(stats["quality_scores"]) / len(
                stats["quality_scores"]
            )
            stats["pass_rate"] = stats["pass_count"] / stats["total_count"]
            stats["avg_retrieval_time"] = (
                sum(stats["retrieval_times"]) / len(stats["retrieval_times"])
                if stats["retrieval_times"]
                else 0
            )
            # Composite score: 70% quality + 20% pass rate + 10% speed bonus (lower time = higher score)
            speed_score = (
                max(0, (100 - stats["avg_retrieval_time"]) / 100)
                if stats["avg_retrieval_time"] > 0
                else 0
            )
            stats["composite_score"] = (
                0.7 * stats["avg_quality"]
                + 0.2 * stats["pass_rate"]
                + 0.1 * speed_score
            )

        # Find best combination by composite score
        if combination_stats:
            best_combo_key = max(
                combination_stats.keys(),
                key=lambda k: combination_stats[k]["composite_score"],
            )
            return {"combo_key": best_combo_key, **combination_stats[best_combo_key]}

        return None

    def generate_summary_report(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult],
    ) -> str:
        """Generate comprehensive summary report."""
        report_lines = [
            "# Retrieval Performance Test Results",
            f"**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "**Language Model:** OpenAI GPT-4o-mini",
            f"**Test Cases:** {len(self.test_cases)}",
            f"**Parameter Combinations:** {len(self.combinations)}",
            "",
            "## Summary Metrics",
        ]

        if evaluation_results:
            successful_evals = [e for e in evaluation_results if e.error is None]
            if successful_evals:
                overall_avg_quality = sum(
                    e.retrieval_quality_score for e in successful_evals
                ) / len(successful_evals)
                overall_pass_rate = sum(
                    1 for e in successful_evals if e.judgment
                ) / len(successful_evals)

                report_lines.extend(
                    [
                        f"- **Overall Average Quality Score:** {overall_avg_quality:.3f}",
                        f"- **Overall Pass Rate:** {overall_pass_rate:.1%}",
                        "",
                    ]
                )

        # Performance by search type
        report_lines.append("## Performance by Search Type")
        for search_type in self.config.search_types:
            type_evals = [
                e
                for e in evaluation_results
                if e.combination.search_type == search_type and e.error is None
            ]
            if type_evals:
                avg_quality = sum(e.retrieval_quality_score for e in type_evals) / len(
                    type_evals
                )
                pass_rate = sum(1 for e in type_evals if e.judgment) / len(type_evals)
                type_retrievals = [
                    r
                    for r in retrieval_results
                    if r.combination.search_type == search_type and r.error is None
                ]
                avg_time = (
                    sum(r.retrieval_time_ms for r in type_retrievals)
                    / len(type_retrievals)
                    if type_retrievals
                    else 0
                )

                report_lines.extend(
                    [
                        f"### {search_type.title()} Search",
                        f"- Quality Score: {avg_quality:.3f}",
                        f"- Pass Rate: {pass_rate:.1%}",
                        f"- Avg Retrieval Time: {avg_time:.1f}ms",
                        "",
                    ]
                )

        # Best combination
        best_combo = self.find_best_combination(retrieval_results, evaluation_results)
        if best_combo:
            report_lines.extend(
                [
                    "## Best Performing Combination",
                    f"**{best_combo['search_type'].title()} search with {best_combo['max_hits']} max hits**",
                    f"- Quality Score: {best_combo['avg_quality']:.3f}",
                    f"- Pass Rate: {best_combo['pass_rate']:.1%}",
                    f"- Avg Retrieval Time: {best_combo['avg_retrieval_time']:.1f}ms",
                    f"- Composite Score: {best_combo['composite_score']:.3f}",
                    "",
                    "*Composite Score = 70% Quality + 20% Pass Rate + 10% Speed Bonus*",
                ]
            )

        return "\n".join(report_lines)


class TestRetrievalPerformance(unittest.TestCase):
    """Test class for retrieval performance evaluation."""

    def test_retrieval_quality_across_search_parameters(self):
        """Comprehensive retrieval quality evaluation across search types and parameters."""
        asyncio.run(_run_retrieval_test())


@pytest.mark.asyncio
async def test_retrieval_quality_async():
    """Async pytest version of the retrieval performance test."""
    await _run_retrieval_test()


async def _run_retrieval_test():
    """Run the actual test logic using staged approach."""
    logger.info("Starting staged retrieval test...")

    config = RetrievalTestConfiguration(
        search_types=["hybrid", "keyword", "vector"],
        max_hits_values=[1, 5, 10],
        parallel_queries=True,
        parallel_evaluations=True,
        max_query_workers=5,
        max_eval_workers=3,
    )

    tester = RetrievalPerformanceTester(config=config)
    logger.info("Tester initialized")

    retrieval_results, evaluation_results = await tester.run_staged_evaluation()

    summary_report = tester.generate_summary_report(
        retrieval_results, evaluation_results
    )
    logger.info("Summary report generated")
    logger.info(f"\n{summary_report}")

    # Find and display best combination
    best_combo = tester.find_best_combination(retrieval_results, evaluation_results)
    if best_combo:
        logger.info("=" * 60)
        logger.info("BEST PERFORMING COMBINATION")
        logger.info("=" * 60)
        logger.info(f"Search Type: {best_combo['search_type'].upper()}")
        logger.info(f"Max Hits: {best_combo['max_hits']}")
        logger.info(f"Quality Score: {best_combo['avg_quality']:.3f}")
        logger.info(f"Pass Rate: {best_combo['pass_rate']:.1%}")
        logger.info(f"Avg Retrieval Time: {best_combo['avg_retrieval_time']:.1f}ms")
        logger.info(f"Composite Score: {best_combo['composite_score']:.3f}")
        logger.info("=" * 60)

        # Recommendation
        if best_combo["avg_quality"] >= 0.8:
            logger.info(
                "RECOMMENDATION: This combination provides excellent retrieval quality!"
            )
        elif best_combo["avg_quality"] >= 0.7:
            logger.info(
                "RECOMMENDATION: This combination provides good retrieval quality."
            )
        else:
            logger.info(
                "RECOMMENDATION: Consider tuning parameters for better quality."
            )

    # Assertions
    logger.info("Performing assertions...")
    assert len(evaluation_results) > 0, "No evaluations were completed"
    assert len(retrieval_results) > 0, "No retrieval results were obtained"

    expected_combinations = (
        len(tester.test_cases) * len(config.search_types) * len(config.max_hits_values)
    )
    assert len(retrieval_results) == expected_combinations, (
        f"Expected {expected_combinations} results, got {len(retrieval_results)}"
    )

    successful_evals = [e for e in evaluation_results if e.error is None]
    if successful_evals:
        avg_quality = sum(e.retrieval_quality_score for e in successful_evals) / len(
            successful_evals
        )
        pass_rate = sum(1 for e in successful_evals if e.judgment) / len(
            successful_evals
        )

        logger.info(f"Overall average quality score: {avg_quality:.3f}")
        logger.info(f"Overall pass rate: {pass_rate:.1%}")

        if avg_quality < 0.6:
            logger.warning(f"Low average quality score: {avg_quality:.3f}")
        if pass_rate < 0.5:
            logger.warning(f"Low pass rate: {pass_rate:.1%}")

    logger.info("Test completed successfully!")


async def main():
    """Main entry point for standalone execution."""
    await _run_retrieval_test()


if __name__ == "__main__":
    asyncio.run(main())
