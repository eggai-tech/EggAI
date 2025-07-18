"""
Retrieval Performance Test Suite

Tests different search configurations to find optimal settings.
Tracks results in MLflow for analysis.
"""
import asyncio
import os
from datetime import datetime
from typing import List, Tuple

import httpx
import pytest

from agents.policies.agent.config import settings as agent_settings
from agents.policies.ingestion.config import settings as ingestion_settings
from agents.policies.ingestion.workflows.activities.document_chunking_activity import (
    chunk_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_indexing_activity import (
    index_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_loading_activity import (
    load_document_activity,
)
from agents.policies.ingestion.workflows.activities.document_verification_activity import (
    verify_document_activity,
)
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
from agents.policies.tests.retrieval_performance.performance_calculator import (
    PerformanceCalculator,
)
from agents.policies.vespa.deploy_package import deploy_to_vespa
from libraries.observability.logger import get_console_logger

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
        
        # Get Vespa URLs for later use
        vespa_config_url = ingestion_settings.vespa_config_url
        vespa_query_url = ingestion_settings.vespa_query_url
        
        # Deploy Vespa schema FIRST (before connectivity checks)
        logger.info("Deploying Vespa schema (before connectivity checks)...")
        deployment_success = deploy_to_vespa(
            config_server_url=vespa_config_url,
            query_url=vespa_query_url,
            force=False,  # Only deploy if schema doesn't exist
            artifacts_dir=ingestion_settings.vespa_artifacts_dir,
            deployment_mode=ingestion_settings.vespa_deployment_mode,
            node_count=ingestion_settings.vespa_node_count,
            hosts_config=ingestion_settings.vespa_hosts_config,
            services_xml=ingestion_settings.vespa_services_xml,
            app_name=ingestion_settings.vespa_app_name_base,
        )
        if not deployment_success:
            logger.error("Failed to deploy Vespa schema")
            return False
        logger.info("✓ Vespa schema deployment completed")
        
        # Check Kafka connectivity using agent config
        kafka_url = agent_settings.kafka_bootstrap_servers
        logger.info(f"Checking Kafka at {kafka_url} (from agent config)...")
        if not await self._check_kafka_connectivity(kafka_url):
            logger.error(f"Kafka not accessible at {kafka_url}")
            return False
        logger.info("✓ Kafka connectivity verified")
        
        # Check Vespa connectivity AFTER deployment
        logger.info(f"Checking Vespa config server at {vespa_config_url} (from ingestion config)...")
        logger.info(f"Checking Vespa query server at {vespa_query_url} (from ingestion config)...")
        if not await self._check_vespa_connectivity(vespa_config_url, vespa_query_url):
            logger.error(f"Vespa not accessible at {vespa_config_url} or {vespa_query_url}")
            return False
        logger.info("✓ Vespa connectivity verified")
        
        # Run document ingestion to populate Vespa with sample data
        logger.info("Running initial document ingestion...")
        ingestion_success = await self.run_document_ingestion()
        if not ingestion_success:
            logger.error("Failed to ingest sample documents")
            return False
        logger.info("✓ Sample documents ingested successfully")
        
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
        logger.info("Agent Settings:")
        logger.info(f"  - App Name: {agent_settings.app_name}")
        logger.info(f"  - Kafka Bootstrap Servers: {agent_settings.kafka_bootstrap_servers}")
        logger.info(f"  - Language Model: {agent_settings.language_model}")
        logger.info("Ingestion Settings:")
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

    async def run_document_ingestion(self, sample_documents_dir: str = None) -> bool:
        """Run document ingestion activities directly without Temporal."""
        if sample_documents_dir is None:
            sample_documents_dir = "agents/policies/ingestion/documents"
        
        logger.info(f"Starting document ingestion from {sample_documents_dir}")
        
        # Find sample documents
        import glob
        from pathlib import Path
        
        doc_pattern = f"{sample_documents_dir}/*.md"
        sample_files = glob.glob(doc_pattern)
        
        if not sample_files:
            logger.warning(f"No sample documents found in {sample_documents_dir}")
            return False
        
        logger.info(f"Found {len(sample_files)} sample documents to ingest")
        
        success_count = 0
        total_chunks = 0
        
        for file_path in sample_files:
            try:
                logger.info(f"Processing document: {file_path}")
                
                # Step 1: Verify document
                verification_result = await verify_document_activity(
                    file_path, "policies_index", force_rebuild=True
                )
                
                if not verification_result["success"]:
                    logger.error(f"Verification failed for {file_path}: {verification_result.get('error_message')}")
                    continue
                
                # Step 2: Load document
                load_result = await load_document_activity(file_path)
                
                if not load_result["success"]:
                    logger.error(f"Loading failed for {file_path}: {load_result.get('error_message')}")
                    continue
                
                # Step 3: Chunk document
                chunk_result = await chunk_document_activity(load_result)
                
                if not chunk_result["success"]:
                    logger.error(f"Chunking failed for {file_path}: {chunk_result.get('error_message')}")
                    continue
                
                if not chunk_result["chunks"]:
                    logger.warning(f"No chunks generated for {file_path}")
                    continue
                
                # Step 4: Index chunks
                # Extract category from filename (e.g., "life.md" -> "life")
                from pathlib import Path
                category = Path(file_path).stem  # Gets "life" from "life.md"
                
                indexing_result = await index_document_activity(
                    chunk_result["chunks"],
                    file_path,
                    category,  # Use filename-based category to match test expectations
                    "policies_index",  # index_name
                    True,  # force_rebuild
                    chunk_result.get("document_stats"),
                    load_result.get("metadata")
                )
                
                if not indexing_result["success"]:
                    logger.error(f"Indexing failed for {file_path}: {indexing_result.get('error_message')}")
                    continue
                
                success_count += 1
                doc_chunks = len(chunk_result["chunks"])
                total_chunks += doc_chunks
                logger.info(f"Successfully ingested {Path(file_path).name} - {doc_chunks} chunks")
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                continue
        
        logger.info(f"Document ingestion completed: {success_count}/{len(sample_files)} documents processed, {total_chunks} total chunks")
        return success_count > 0

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
    """Async pytest version of the retrieval performance test with 8-minute timeout."""
    try:
        await asyncio.wait_for(_run_retrieval_test(), timeout=480)
    except asyncio.TimeoutError:
        pytest.fail("Test timed out after 8 minutes")


async def _run_retrieval_test():
    """Run the actual test logic using 4-stage approach."""
    logger.info("Starting 4-stage retrieval test with 8-minute timeout...")

    # Check if OPENAI_API_KEY is available for LLM judge
    enable_llm_judge = bool(os.getenv("OPENAI_API_KEY"))
    if not enable_llm_judge:
        logger.warning("OPENAI_API_KEY not set, disabling LLM judge for evaluation")
    
    config = RetrievalTestConfiguration(
        search_types=["hybrid", "keyword", "vector"],
        max_hits_values=[1, 5, 10],
        max_query_workers=5,
        max_eval_workers=3,
        enable_llm_judge=enable_llm_judge  # Conditionally enable based on API key
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
        ) = await asyncio.wait_for(tester.run_full_evaluation(), timeout=475)  # Leave 5s buffer for cleanup
        logger.info("Evaluation completed within timeout")
    except asyncio.TimeoutError:
        logger.error("Test evaluation timed out after 475 seconds")
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

    # Find and display best combination using unified performance calculator
    calculator = PerformanceCalculator(has_llm_judge=bool(evaluation_results))
    best_combo = calculator.find_best_combination(retrieval_results, evaluation_results)
    
    if best_combo:
        logger.info("=" * 60)
        llm_suffix = " (WITH LLM JUDGE)" if evaluation_results else " (RETRIEVAL-ONLY)"
        logger.info(f"BEST PERFORMING COMBINATION{llm_suffix}")
        logger.info("=" * 60)
        logger.info(f"Search Type: {best_combo.search_type.upper()}")
        logger.info(f"Max Hits: {best_combo.max_hits}")
        logger.info(f"Final Score: {best_combo.final_score:.3f}")
        logger.info("")
        
        # Display key metrics
        logger.info("Key Metrics:")
        logger.info(f"  • Success Rate: {best_combo.metrics.get('success_rate', 0):.1%}")
        logger.info(f"  • Avg Retrieval Time: {best_combo.metrics.get('avg_retrieval_time', 0):.1f}ms")
        logger.info(f"  • Avg Total Hits: {best_combo.metrics.get('avg_total_hits', 0):.1f}")
        
        if evaluation_results:
            logger.info(f"  • Avg Quality Score: {best_combo.metrics.get('avg_quality_score', 0):.3f}")
            logger.info(f"  • Pass Rate: {best_combo.metrics.get('pass_rate', 0):.1%}")
            logger.info(f"  • Avg Recall: {best_combo.metrics.get('avg_recall_score', 0):.3f}")
            logger.info(f"  • Hit Rate Top 3: {best_combo.metrics.get('hit_rate_top_3', 0):.1%}")
        
        logger.info("=" * 60)
        
        # Recommendation based on performance score
        if best_combo.final_score >= 0.8:
            logger.info("RECOMMENDATION: Excellent overall performance!")
        elif best_combo.final_score >= 0.6:
            logger.info("RECOMMENDATION: Good overall performance.")
        elif best_combo.final_score >= 0.4:
            logger.info("RECOMMENDATION: Moderate performance - consider parameter tuning.")
        else:
            logger.info("RECOMMENDATION: Poor performance - significant optimization needed.")
            
        # Warning if no LLM judge
        if not evaluation_results:
            logger.warning("")
            logger.warning("⚠️  WARNING: Test ran without LLM quality evaluation!")
            logger.warning("⚠️  Results may be misleading - only retrieval metrics were used.")
            logger.warning("⚠️  For accurate results, ensure OPENAI_API_KEY is set and enable_llm_judge=True")
        
        # Log metrics summary
        metrics_summary = calculator.get_metrics_summary()
        logger.info(f"Performance calculated using {metrics_summary['total_metrics']} metrics")
        for category, metrics_list in metrics_summary['metrics_by_category'].items():
            category_weight = sum(m['weight'] for m in metrics_list)
            logger.info(f"  • {category.title()}: {category_weight:.1%} total weight")

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
        await asyncio.wait_for(_run_retrieval_test(), timeout=480)
        logger.info("Standalone test completed successfully")
    except asyncio.TimeoutError:
        logger.error("Standalone test timed out after 8 minutes")
        raise


if __name__ == "__main__":
    asyncio.run(main())
