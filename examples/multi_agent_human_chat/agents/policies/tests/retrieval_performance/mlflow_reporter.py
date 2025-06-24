"""MLflow reporting for retrieval performance results."""

from datetime import datetime
from typing import List

import mlflow

from libraries.logger import get_console_logger

from .models import EvaluationResult, RetrievalResult

logger = get_console_logger("mlflow_reporter")


class MLflowReporter:
    """Reports retrieval performance results to MLflow."""
    
    def __init__(self):
        experiment_name = "retrieval_performance_evaluation"
        mlflow.set_experiment(experiment_name)
    
    def report_results(self, retrieval_results: List[RetrievalResult], evaluation_results: List[EvaluationResult]) -> None:
        """Report results with one run per parameter combination."""
        logger.info(f"📊 Stage 3: Reporting {len(evaluation_results)} results to MLflow")
        
        try:
            experiment_name = "retrieval_performance_evaluation"
            mlflow.set_experiment(experiment_name)
            
            combination_groups = self._group_by_combination(retrieval_results, evaluation_results)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for combo_name, combo_data in combination_groups.items():
                self._log_combination_run(combo_name, combo_data, timestamp)
            
            logger.info(f"✅ Stage 3 completed: {len(combination_groups)} runs logged to experiment '{experiment_name}'")
        
        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
    
    def _group_by_combination(self, retrieval_results: List[RetrievalResult], evaluation_results: List[EvaluationResult]) -> dict:
        """Group results by parameter combination."""
        combination_groups = {}
        
        for eval_result in evaluation_results:
            combo_key = f"{eval_result.combination.search_type}_hits{eval_result.combination.max_hits}"
            if combo_key not in combination_groups:
                combination_groups[combo_key] = {"evaluations": [], "retrievals": []}
            
            combination_groups[combo_key]["evaluations"].append(eval_result)
            
            matching_retrieval = next(
                (r for r in retrieval_results 
                 if (r.combination.test_case_id == eval_result.combination.test_case_id
                     and r.combination.search_type == eval_result.combination.search_type
                     and r.combination.max_hits == eval_result.combination.max_hits)),
                None
            )
            
            if matching_retrieval:
                combination_groups[combo_key]["retrievals"].append(matching_retrieval)
        
        return combination_groups
    
    def _log_combination_run(self, combo_name: str, combo_data: dict, timestamp: str) -> None:
        """Log a single combination run to MLflow."""
        try:
            run_name = f"{combo_name}_{timestamp}"
            
            with mlflow.start_run(run_name=run_name):
                evaluations = combo_data["evaluations"]
                retrievals = combo_data["retrievals"]
                
                if evaluations:
                    self._log_parameters(evaluations[0])
                    self._log_aggregate_metrics(evaluations, retrievals)
                    self._log_individual_metrics(evaluations, retrievals)
                
                logger.info(f"✅ Logged run: {run_name} (tested {len(evaluations)} test cases)")
        
        except Exception as e:
            logger.error(f"Failed to log run {combo_name}: {e}")
    
    def _log_parameters(self, eval_sample):
        """Log run parameters."""
        mlflow.log_param("search_type", eval_sample.combination.search_type)
        mlflow.log_param("max_hits", eval_sample.combination.max_hits)
        mlflow.log_param("test_run_timestamp", datetime.now().isoformat())
    
    def _log_aggregate_metrics(self, evaluations: List[EvaluationResult], retrievals: List[RetrievalResult]) -> None:
        """Log aggregate metrics."""
        mlflow.log_param("num_test_cases", len(evaluations))
        
        # Evaluation metrics
        avg_quality = sum(e.retrieval_quality_score for e in evaluations) / len(evaluations)
        avg_completeness = sum(e.completeness_score for e in evaluations) / len(evaluations)
        avg_relevance = sum(e.relevance_score for e in evaluations) / len(evaluations)
        pass_rate = sum(1 for e in evaluations if e.judgment) / len(evaluations)
        avg_eval_time = sum(e.evaluation_time_ms for e in evaluations) / len(evaluations)
        
        mlflow.log_metric("avg_quality_score", avg_quality)
        mlflow.log_metric("avg_completeness_score", avg_completeness)
        mlflow.log_metric("avg_relevance_score", avg_relevance)
        mlflow.log_metric("pass_rate", pass_rate)
        mlflow.log_metric("avg_evaluation_time_ms", avg_eval_time)
        
        # Retrieval metrics
        if retrievals:
            avg_retrieval_time = sum(r.retrieval_time_ms for r in retrievals) / len(retrievals)
            avg_total_hits = sum(r.total_hits for r in retrievals) / len(retrievals)
            error_rate = sum(1 for r in retrievals if r.error) / len(retrievals)
            
            mlflow.log_metric("avg_retrieval_time_ms", avg_retrieval_time)
            mlflow.log_metric("avg_total_hits", avg_total_hits)
            mlflow.log_metric("error_rate", error_rate)
    
    def _log_individual_metrics(self, evaluations: List[EvaluationResult], retrievals: List[RetrievalResult]) -> None:
        """Log individual test case metrics."""
        for eval_result in evaluations:
            test_case_id = eval_result.combination.test_case_id
            
            # Evaluation metrics per test case
            mlflow.log_metric(f"quality_score_{test_case_id}", eval_result.retrieval_quality_score)
            mlflow.log_metric(f"completeness_{test_case_id}", eval_result.completeness_score)
            mlflow.log_metric(f"relevance_{test_case_id}", eval_result.relevance_score)
            mlflow.log_metric(f"judgment_{test_case_id}", 1.0 if eval_result.judgment else 0.0)
            
            # Retrieval metrics per test case
            matching_retrieval = next(
                (r for r in retrievals if r.combination.test_case_id == test_case_id), None
            )
            if matching_retrieval:
                mlflow.log_metric(f"retrieval_time_{test_case_id}", matching_retrieval.retrieval_time_ms)
                mlflow.log_metric(f"total_hits_{test_case_id}", matching_retrieval.total_hits)