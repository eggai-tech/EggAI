"""
Unified Performance Calculator

This module provides a unified approach to calculating performance scores
for retrieval combinations, regardless of whether LLM judge is enabled.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from libraries.observability.logger import get_console_logger

from .metrics_config import (
    NORMALIZATION_FUNCTIONS,
    get_active_metrics,
    normalize_weights,
)
from .models import EvaluationResult, RetrievalResult

logger = get_console_logger("performance_calculator")


@dataclass
class CombinationStats:
    """Statistics for a parameter combination."""
    search_type: str
    max_hits: int
    combo_key: str
    
    # Raw data
    retrieval_results: List[RetrievalResult]
    evaluation_results: List[EvaluationResult]
    
    # Calculated metrics
    metrics: Dict[str, float]
    normalized_metrics: Dict[str, float]
    final_score: float
    
    # Metadata
    total_queries: int
    successful_queries: int


class PerformanceCalculator:
    """Unified performance calculator for retrieval combinations."""
    
    def __init__(self, has_llm_judge: bool = False):
        """Initialize calculator with configuration based on available data."""
        self.has_llm_judge = has_llm_judge
        self.active_metrics = get_active_metrics(has_llm_judge)
        self.normalized_metrics = normalize_weights(self.active_metrics)
        
        logger.info(f"Performance calculator initialized (LLM judge: {has_llm_judge})")
        logger.info(f"Active metrics: {list(self.active_metrics.keys())}")
    
    def calculate_combination_stats(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult] = None
    ) -> Dict[str, CombinationStats]:
        """Calculate statistics for all parameter combinations."""
        
        # Group results by combination
        combinations = self._group_by_combination(retrieval_results, evaluation_results or [])
        
        # Calculate stats for each combination
        combination_stats = {}
        for combo_key, (retrievals, evaluations) in combinations.items():
            stats = self._calculate_single_combination(combo_key, retrievals, evaluations)
            combination_stats[combo_key] = stats
        
        return combination_stats
    
    def find_best_combination(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult] = None
    ) -> Optional[CombinationStats]:
        """Find the best performing combination."""
        
        combination_stats = self.calculate_combination_stats(retrieval_results, evaluation_results)
        
        if not combination_stats:
            return None
        
        # Find combination with highest final score
        best_combo_key = max(combination_stats.keys(), key=lambda k: combination_stats[k].final_score)
        best_stats = combination_stats[best_combo_key]
        
        logger.info(f"Best combination: {best_combo_key} (score: {best_stats.final_score:.3f})")
        
        return best_stats
    
    def _group_by_combination(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult]
    ) -> Dict[str, tuple]:
        """Group results by parameter combination."""
        
        combinations = {}
        
        # Group retrieval results
        for result in retrieval_results:
            combo_key = f"{result.combination.search_type}_hits{result.combination.max_hits}"
            if combo_key not in combinations:
                combinations[combo_key] = ([], [])
            combinations[combo_key][0].append(result)
        
        # Group evaluation results (if available)
        for result in evaluation_results:
            combo_key = f"{result.combination.search_type}_hits{result.combination.max_hits}"
            if combo_key in combinations:
                combinations[combo_key][1].append(result)
        
        return combinations
    
    def _calculate_single_combination(
        self,
        combo_key: str,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult]
    ) -> CombinationStats:
        """Calculate statistics for a single combination."""
        
        # Extract combination info
        if retrieval_results:
            combo = retrieval_results[0].combination
            search_type = combo.search_type
            max_hits = combo.max_hits
        else:
            # Fallback parsing
            parts = combo_key.split('_hits')
            search_type = parts[0]
            max_hits = int(parts[1])
        
        # Calculate raw metrics
        raw_metrics = self._calculate_raw_metrics(retrieval_results, evaluation_results, max_hits)
        
        # Normalize metrics
        normalized_metrics = self._normalize_metrics(raw_metrics, max_hits)
        
        # Calculate final score
        final_score = self._calculate_final_score(normalized_metrics)
        
        return CombinationStats(
            search_type=search_type,
            max_hits=max_hits,
            combo_key=combo_key,
            retrieval_results=retrieval_results,
            evaluation_results=evaluation_results,
            metrics=raw_metrics,
            normalized_metrics=normalized_metrics,
            final_score=final_score,
            total_queries=len(retrieval_results),
            successful_queries=len([r for r in retrieval_results if r.error is None])
        )
    
    def _calculate_raw_metrics(
        self,
        retrieval_results: List[RetrievalResult],
        evaluation_results: List[EvaluationResult],
        max_hits: int
    ) -> Dict[str, float]:
        """Calculate raw metric values."""
        
        metrics = {}
        
        # Retrieval metrics
        successful_retrievals = [r for r in retrieval_results if r.error is None]
        
        if retrieval_results:
            metrics["success_rate"] = len(successful_retrievals) / len(retrieval_results)
        else:
            metrics["success_rate"] = 0.0
        
        if successful_retrievals:
            metrics["avg_total_hits"] = sum(r.total_hits for r in successful_retrievals) / len(successful_retrievals)
            metrics["avg_retrieval_time"] = sum(r.retrieval_time_ms for r in successful_retrievals) / len(successful_retrievals)
        else:
            metrics["avg_total_hits"] = 0.0
            metrics["avg_retrieval_time"] = 0.0
        
        # LLM Judge metrics (if available)
        if evaluation_results and self.has_llm_judge:
            successful_evaluations = [e for e in evaluation_results if e.error is None]
            
            if successful_evaluations:
                metrics["avg_quality_score"] = sum(e.retrieval_quality_score for e in successful_evaluations) / len(successful_evaluations)
                metrics["pass_rate"] = sum(1 for e in successful_evaluations if e.judgment) / len(successful_evaluations)
                metrics["avg_completeness_score"] = sum(e.completeness_score for e in successful_evaluations) / len(successful_evaluations)
                
                # Context-based metrics
                metrics["avg_recall_score"] = sum(e.recall_score for e in successful_evaluations) / len(successful_evaluations)
                metrics["avg_precision_at_k"] = sum(e.precision_at_k for e in successful_evaluations) / len(successful_evaluations)
                metrics["avg_ndcg_score"] = sum(e.ndcg_score for e in successful_evaluations) / len(successful_evaluations)
                
                # Position-based metrics
                positions = [e.best_match_position for e in successful_evaluations if e.best_match_position is not None]
                if positions:
                    metrics["avg_best_position"] = sum(positions) / len(positions)
                    metrics["hit_rate_top_3"] = sum(1 for p in positions if p <= 3) / len(successful_evaluations)
                else:
                    metrics["avg_best_position"] = 0.0
                    metrics["hit_rate_top_3"] = 0.0
            else:
                # Set default values for LLM metrics
                for key in ["avg_quality_score", "pass_rate", "avg_completeness_score", 
                           "avg_recall_score", "avg_precision_at_k", "avg_ndcg_score",
                           "avg_best_position", "hit_rate_top_3"]:
                    metrics[key] = 0.0
        
        return metrics
    
    def _normalize_metrics(self, raw_metrics: Dict[str, float], max_hits: int) -> Dict[str, float]:
        """Normalize metrics to 0-1 scale."""
        
        normalized = {}
        context = {"max_hits": max_hits}
        
        for metric_key, value in raw_metrics.items():
            if metric_key in self.normalized_metrics:
                metric_def = self.normalized_metrics[metric_key]
                normalize_fn = NORMALIZATION_FUNCTIONS[metric_def.normalize_fn]
                normalized_value = normalize_fn(value, context)
                
                # Invert if lower is better
                if not metric_def.higher_is_better:
                    normalized_value = 1.0 - normalized_value
                
                normalized[metric_key] = normalized_value
        
        return normalized
    
    def _calculate_final_score(self, normalized_metrics: Dict[str, float]) -> float:
        """Calculate weighted final score."""
        
        total_score = 0.0
        
        for metric_key, normalized_value in normalized_metrics.items():
            if metric_key in self.normalized_metrics:
                weight = self.normalized_metrics[metric_key].weight
                contribution = weight * normalized_value
                total_score += contribution
        
        return total_score
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of active metrics and their weights."""
        
        summary = {
            "has_llm_judge": self.has_llm_judge,
            "total_metrics": len(self.normalized_metrics),
            "metrics_by_category": {},
            "total_weight": sum(m.weight for m in self.normalized_metrics.values())
        }
        
        # Group by category
        for metric in self.normalized_metrics.values():
            category = metric.category.value
            if category not in summary["metrics_by_category"]:
                summary["metrics_by_category"][category] = []
            
            summary["metrics_by_category"][category].append({
                "key": metric.key,
                "name": metric.name,
                "weight": metric.weight,
                "weight_percentage": f"{metric.weight * 100:.1f}%"
            })
        
        return summary