"""
Retrieval Performance Test Suite

4-stage testing: Collect -> Metrics -> LLM Judge -> Report
Results logged to MLflow for tracking and analysis.
"""
import asyncio
import os
import unittest
from datetime import datetime
from typing import List, Tuple

import httpx
import pytest

from agents.policies.agent.config import settings as agent_settings
from agents.policies.ingestion.config import settings as ingestion_settings
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

# Development constants
LIMIT_DATASET_ITEMS = os.getenv("LIMIT_DATASET_ITEMS", "2")
if LIMIT_DATASET_ITEMS is not None:
    LIMIT_DATASET_ITEMS = int(LIMIT_DATASET_ITEMS)


class RetrievalPerformanceTester:
    """Orchestrates 4-stage retrieval performance testing."""

    def __init__(
        self,
        config: RetrievalTestConfiguration = None,
    ):
        self.config = config or RetrievalTestConfiguration()
        self.test_cases = get_retrieval_test_cases()

        # Apply dataset limit for development
        if LIMIT_DATASET_ITEMS is not None:
            original_count = len(self.test_cases)
            self.test_cases = self.test_cases[:LIMIT_DATASET_ITEMS]
            logger.info(
                f"DEV MODE: Limited dataset from {original_count} to {len(self.test_cases)} items"
            )

        self.combinations = self._generate_combinations()

        self.api_client = RetrievalAPIClient()
        self.evaluator = RetrievalEvaluator(
            enable_llm_judge=self.config.enable_llm_judge
        )
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

    async def check_service_prerequisites(self) -> bool:
        """Check infrastructure prerequisites and start embedded service for testing."""
        logger.info("Checking infrastructure prerequisites using configuration settings...")
        
        # Log configuration being used
        self._log_configuration()
        
        # Check Kafka connectivity using agent config
        kafka_url = agent_settings.kafka_bootstrap_servers
        logger.info(f"Checking Kafka at {kafka_url} (from agent config)...")
        if not await self._check_kafka_connectivity(kafka_url):
            logger.error(f"Kafka not accessible at {kafka_url}")
            return False
        logger.info("✓ Kafka connectivity verified")
        
        # Check Vespa connectivity using ingestion config
        vespa_config_url = ingestion_settings.vespa_config_url
        vespa_query_url = ingestion_settings.vespa_query_url
        logger.info(f"Checking Vespa config server at {vespa_config_url} (from ingestion config)...")
        logger.info(f"Checking Vespa query server at {vespa_query_url} (from ingestion config)...")
        if not await self._check_vespa_connectivity(vespa_config_url, vespa_query_url):
            logger.error(f"Vespa not accessible at {vespa_config_url} or {vespa_query_url}")
            return False
        logger.info("✓ Vespa connectivity verified")
        
        # Start embedded service
        logger.info("Starting embedded service for testing...")
        success = await self.api_client.start_service()
        if not success:
            logger.error("Failed to start embedded service for testing")
            return False

        logger.info(f"✓ Service ready at {self.api_client.base_url}")
        return True
    
    def _log_configuration(self) -> None:
        """Log the configuration being used for service checks."""
        logger.info("=== Configuration for Infrastructure Checks ===")
        logger.info(f"Agent Settings:")
        logger.info(f"  - App Name: {agent_settings.app_name}")
        logger.info(f"  - Kafka Bootstrap Servers: {agent_settings.kafka_bootstrap_servers}")
        logger.info(f"  - Language Model: {agent_settings.language_model}")
        logger.info(f"Ingestion Settings:")
        logger.info(f"  - App Name: {ingestion_settings.app_name}")
        logger.info(f"  - Vespa Config URL: {ingestion_settings.vespa_config_url}")
        logger.info(f"  - Vespa Query URL: {ingestion_settings.vespa_query_url}")
        logger.info(f"  - Vespa App Name: {ingestion_settings.vespa_app_name}")
        logger.info(f"  - Deployment Mode: {ingestion_settings.vespa_deployment_mode}")
        logger.info(f"  - Temporal Server: {ingestion_settings.temporal_server_url}")
        logger.info(f"  - Temporal Namespace: {ingestion_settings.get_temporal_namespace()}")
        logger.info("=" * 50)
        
        # Validate critical configuration
        if not agent_settings.kafka_bootstrap_servers:
            logger.warning("Kafka bootstrap servers not configured!")
        if not ingestion_settings.vespa_config_url:
            logger.warning("Vespa config URL not configured!")
        if not ingestion_settings.vespa_query_url:
            logger.warning("Vespa query URL not configured!")
    
    async def _check_kafka_connectivity(self, kafka_url: str) -> bool:
        """Check if Kafka is accessible."""
        try:
            # Try to connect to Kafka bootstrap servers
            # We'll use a simple socket check since we don't want to add kafka-python dependency
            import socket
            host, port = kafka_url.split(":")
            port = int(port)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                logger.info(f"Kafka port {port} is accessible on {host}")
                return True
            else:
                logger.warning(f"Kafka port {port} not accessible on {host}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking Kafka connectivity: {e}")
            return False
    
    async def _check_vespa_connectivity(self, config_url: str, query_url: str) -> bool:
        """Check if Vespa is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check config server
                logger.info(f"Testing Vespa config server: {config_url}")
                config_response = await client.get(f"{config_url}/status.html")
                if config_response.status_code != 200:
                    logger.warning(f"Vespa config server returned status {config_response.status_code}")
                    return False
                logger.info("Config server responded successfully")
                
                # Check query service
                logger.info(f"Testing Vespa query service: {query_url}")
                query_response = await client.get(f"{query_url}/status.html")
                if query_response.status_code != 200:
                    logger.warning(f"Vespa query service returned status {query_response.status_code}")
                    return False
                logger.info("Query service responded successfully")
                
                return True
                
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Vespa: {e}")
            return False
        except httpx.TimeoutException as e:
            logger.error(f"Vespa connection timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking Vespa connectivity: {e}")
            return False

    async def stage1_collect_all_results(self) -> List[RetrievalResult]:
        """Stage 1: Collect all retrieved results."""
        logger.info(
            f"Stage 1: Collecting retrieval results for {len(self.combinations)} combinations"
        )

        semaphore = asyncio.Semaphore(self.config.max_query_workers)

        async def query_combination(combination):
            async with semaphore:
                test_case = next(
                    tc for tc in self.test_cases if tc.id == combination.test_case_id
                )
                return await self.api_client.query_single(combination, test_case)

        final_results = await asyncio.gather(
            *[query_combination(combination) for combination in self.combinations]
        )

        successful = len([r for r in final_results if r.error is None])
        logger.info(
            f"Stage 1 completed: {successful}/{len(final_results)} queries successful"
        )
        return final_results

    def stage2_generate_metrics(self, retrieval_results: List[RetrievalResult]) -> dict:
        """Stage 2: Generate metrics from retrieval results."""
        logger.info(f"Stage 2: Generating metrics for {len(retrieval_results)} results")

        metrics = {
            "total_queries": len(retrieval_results),
            "successful_queries": len(
                [r for r in retrieval_results if r.error is None]
            ),
            "failed_queries": len(
                [r for r in retrieval_results if r.error is not None]
            ),
            "avg_retrieval_time_ms": 0.0,
            "total_hits": 0,
            "by_search_type": {},
            "by_max_hits": {},
        }

        successful_results = [r for r in retrieval_results if r.error is None]

        if successful_results:
            metrics["avg_retrieval_time_ms"] = sum(
                r.retrieval_time_ms for r in successful_results
            ) / len(successful_results)
            metrics["total_hits"] = sum(r.total_hits for r in successful_results)

            # Metrics by search type
            for search_type in self.config.search_types:
                type_results = [
                    r
                    for r in successful_results
                    if r.combination.search_type == search_type
                ]
                if type_results:
                    metrics["by_search_type"][search_type] = {
                        "count": len(type_results),
                        "avg_time_ms": sum(r.retrieval_time_ms for r in type_results)
                        / len(type_results),
                        "total_hits": sum(r.total_hits for r in type_results),
                    }

            # Metrics by max hits
            for max_hits in self.config.max_hits_values:
                hits_results = [
                    r for r in successful_results if r.combination.max_hits == max_hits
                ]
                if hits_results:
                    metrics["by_max_hits"][max_hits] = {
                        "count": len(hits_results),
                        "avg_time_ms": sum(r.retrieval_time_ms for r in hits_results)
                        / len(hits_results),
                        "total_hits": sum(r.total_hits for r in hits_results),
                    }

        logger.info(
            f"Stage 2 completed: Generated metrics for {metrics['successful_queries']} successful queries"
        )
        return metrics

    async def stage3_llm_judge(
        self, retrieval_results: List[RetrievalResult]
    ) -> List[EvaluationResult]:
        """Stage 3 (optional): LLM Judge evaluation."""
        logger.info(
            f"Stage 3: LLM Judge evaluation for {len(retrieval_results)} results"
        )

        semaphore = asyncio.Semaphore(self.config.max_eval_workers)

        async def evaluate_result(retrieval_result):
            async with semaphore:
                test_case = next(
                    tc
                    for tc in self.test_cases
                    if tc.id == retrieval_result.combination.test_case_id
                )
                return await self.evaluator.evaluate_single(retrieval_result, test_case)

        final_results = await asyncio.gather(
            *[evaluate_result(result) for result in retrieval_results]
        )

        successful = len([r for r in final_results if r.error is None])
        logger.info(
            f"Stage 3 completed: {successful}/{len(final_results)} evaluations successful"
        )
        return final_results

    def stage4_report_to_mlflow(
        self,
        retrieval_results: List[RetrievalResult],
        metrics: dict,
        evaluation_results: List[EvaluationResult] = None,
    ) -> None:
        """Stage 4: Report to MLflow."""
        logger.info("Stage 4: Reporting to MLflow")
        self.reporter.report_results(
            retrieval_results, evaluation_results or [], self.config
        )

    async def run_full_evaluation(
        self,
    ) -> Tuple[List[RetrievalResult], dict, List[EvaluationResult]]:
        """Run complete 4-stage evaluation: Prerequisites -> Collect -> Metrics -> Judge -> Report."""
        # Prerequisites check
        if not await self.check_service_prerequisites():
            raise RuntimeError(
                "Service prerequisites not met - failed to start API service"
            )

        logger.info("Starting 4-stage retrieval evaluation")
        logger.info(
            f"{len(self.test_cases)} test cases, {len(self.combinations)} total combinations"
        )

        # Stage 1: Collect all retrieved results
        retrieval_results = await self.stage1_collect_all_results()

        # Stage 2: Generate metrics
        metrics = self.stage2_generate_metrics(retrieval_results)

        # Stage 3: LLM Judge (optional)
        evaluation_results = []
        if self.config.enable_llm_judge:
            evaluation_results = await self.stage3_llm_judge(retrieval_results)

        # Stage 4: Report to MLflow
        self.stage4_report_to_mlflow(retrieval_results, metrics, evaluation_results)

        logger.info("4-stage evaluation completed successfully")
        return retrieval_results, metrics, evaluation_results

    def cleanup(self):
        """Clean up resources."""
        self.api_client.stop_service()

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


@pytest.mark.asyncio
async def test_retrieval_performance():
    """Async pytest version of the retrieval performance test with 2-minute timeout."""
    try:
        await asyncio.wait_for(_run_retrieval_test(), timeout=120)
    except asyncio.TimeoutError:
        pytest.fail("Test timed out after 2 minutes")


async def _run_retrieval_test():
    """Run the actual test logic using 4-stage approach."""
    logger.info("Starting 4-stage retrieval test with 2-minute timeout...")

    config = RetrievalTestConfiguration(
        search_types=["hybrid", "keyword", "vector"],
        max_hits_values=[1, 5, 10],
        max_query_workers=5,
        max_eval_workers=3,
    )

    tester = RetrievalPerformanceTester(config=config)
    logger.info("Tester initialized")

    try:
        # Wrap the evaluation with timeout
        logger.info("Starting evaluation with timeout protection...")
        (
            retrieval_results,
            metrics,
            evaluation_results,
        ) = await asyncio.wait_for(tester.run_full_evaluation(), timeout=115)  # Leave 5s buffer for cleanup
        logger.info("Evaluation completed within timeout")
    except asyncio.TimeoutError:
        logger.error("Test evaluation timed out after 115 seconds")
        raise RuntimeError("Test evaluation timed out - check infrastructure connectivity")
    finally:
        logger.info("Cleaning up test resources...")
        tester.cleanup()

    # Log metrics from Stage 2
    logger.info("Stage 2 Metrics:")
    logger.info(f"Total queries: {metrics['total_queries']}")
    logger.info(f"Successful queries: {metrics['successful_queries']}")
    logger.info(f"Average retrieval time: {metrics['avg_retrieval_time_ms']:.1f}ms")
    logger.info(f"Total hits: {metrics['total_hits']}")

    # Generate summary report if LLM judge was used
    if evaluation_results:
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
    assert len(retrieval_results) > 0, "No retrieval results were obtained"

    expected_combinations = (
        len(tester.test_cases) * len(config.search_types) * len(config.max_hits_values)
    )
    assert len(retrieval_results) == expected_combinations, (
        f"Expected {expected_combinations} results, got {len(retrieval_results)}"
    )

    if evaluation_results:
        successful_evals = [e for e in evaluation_results if e.error is None]
        if successful_evals:
            avg_quality = sum(
                e.retrieval_quality_score for e in successful_evals
            ) / len(successful_evals)
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
    logger.info("Running retrieval performance test in standalone mode...")
    try:
        await asyncio.wait_for(_run_retrieval_test(), timeout=120)
        logger.info("Standalone test completed successfully")
    except asyncio.TimeoutError:
        logger.error("Standalone test timed out after 2 minutes")
        raise


if __name__ == "__main__":
    asyncio.run(main())
