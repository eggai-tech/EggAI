"""
Retrieval Performance Metrics Configuration

This file defines all metrics used for evaluating retrieval performance
and their respective weights in the final performance score calculation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class MetricCategory(Enum):
    """Categories of metrics for organization."""
    RETRIEVAL = "retrieval"  # Basic retrieval metrics
    LLM_JUDGE = "llm_judge"  # LLM-based evaluation metrics
    CONTEXT = "context"      # Context-based metrics (precision, recall, etc.)
    POSITION = "position"    # Position-based metrics (ranking quality)


@dataclass
class MetricDefinition:
    """Definition of a performance metric."""
    key: str
    name: str
    description: str
    category: MetricCategory
    weight: float
    normalize_fn: str  # Function name for normalization
    higher_is_better: bool = True


# Metric definitions with weights
METRICS_CONFIG: Dict[str, MetricDefinition] = {
    # Retrieval Metrics (30% total weight)
    "success_rate": MetricDefinition(
        key="success_rate",
        name="Success Rate",
        description="Percentage of queries that return results without errors",
        category=MetricCategory.RETRIEVAL,
        weight=0.15,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    "avg_total_hits": MetricDefinition(
        key="avg_total_hits",
        name="Average Total Hits",
        description="Average number of documents retrieved per query",
        category=MetricCategory.RETRIEVAL,
        weight=0.10,
        normalize_fn="hits_normalization",  # Normalize based on max_hits
        higher_is_better=True
    ),
    
    "avg_retrieval_time": MetricDefinition(
        key="avg_retrieval_time",
        name="Average Retrieval Time",
        description="Average time taken to retrieve results (milliseconds)",
        category=MetricCategory.RETRIEVAL,
        weight=0.05,
        normalize_fn="speed_normalization",  # Faster is better
        higher_is_better=False
    ),
    
    # LLM Judge Metrics (40% total weight when available)
    "avg_quality_score": MetricDefinition(
        key="avg_quality_score",
        name="Average Quality Score",
        description="Average quality score from LLM judge evaluation",
        category=MetricCategory.LLM_JUDGE,
        weight=0.20,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    "pass_rate": MetricDefinition(
        key="pass_rate",
        name="Pass Rate",
        description="Percentage of queries that pass LLM judge evaluation",
        category=MetricCategory.LLM_JUDGE,
        weight=0.15,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    "avg_completeness_score": MetricDefinition(
        key="avg_completeness_score",
        name="Average Completeness Score",
        description="Average completeness score from LLM judge",
        category=MetricCategory.LLM_JUDGE,
        weight=0.05,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    # Context-based Metrics (20% total weight when available)
    "avg_recall_score": MetricDefinition(
        key="avg_recall_score",
        name="Average Recall Score",
        description="Average recall score based on context matching",
        category=MetricCategory.CONTEXT,
        weight=0.08,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    "avg_precision_at_k": MetricDefinition(
        key="avg_precision_at_k",
        name="Average Precision@K",
        description="Average precision at K based on context matching",
        category=MetricCategory.CONTEXT,
        weight=0.07,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    "avg_ndcg_score": MetricDefinition(
        key="avg_ndcg_score",
        name="Average NDCG Score",
        description="Average Normalized Discounted Cumulative Gain",
        category=MetricCategory.CONTEXT,
        weight=0.05,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
    
    # Position-based Metrics (10% total weight when available)
    "avg_best_position": MetricDefinition(
        key="avg_best_position",
        name="Average Best Match Position",
        description="Average position of best matching result",
        category=MetricCategory.POSITION,
        weight=0.05,
        normalize_fn="position_normalization",  # Lower position is better
        higher_is_better=False
    ),
    
    "hit_rate_top_3": MetricDefinition(
        key="hit_rate_top_3",
        name="Hit Rate Top 3",
        description="Percentage of queries with relevant results in top 3",
        category=MetricCategory.POSITION,
        weight=0.05,
        normalize_fn="identity",  # Already 0-1
        higher_is_better=True
    ),
}


# Normalization functions
def identity(value: float, context: Dict[str, Any] = None) -> float:
    """Identity normalization - value is already normalized (0-1)."""
    return max(0.0, min(1.0, value))


def hits_normalization(value: float, context: Dict[str, Any] = None) -> float:
    """Normalize hit count based on max_hits parameter."""
    if context and "max_hits" in context:
        max_hits = context["max_hits"]
        return min(1.0, value / max_hits) if max_hits > 0 else 0.0
    else:
        # Fallback: assume 10+ hits is excellent
        return min(1.0, value / 10.0)


def speed_normalization(value: float, context: Dict[str, Any] = None) -> float:
    """Normalize retrieval time - faster is better."""
    # Assume 2000ms is poor, 0ms is perfect
    max_acceptable_time = 2000.0
    return max(0.0, (max_acceptable_time - value) / max_acceptable_time)


def position_normalization(value: float, context: Dict[str, Any] = None) -> float:
    """Normalize position - lower position is better."""
    if value <= 0:
        return 0.0
    # Assume position 1 is perfect (1.0), position 10+ is poor (0.0)
    max_acceptable_position = 10.0
    return max(0.0, (max_acceptable_position - value + 1) / max_acceptable_position)


# Available normalization functions
NORMALIZATION_FUNCTIONS = {
    "identity": identity,
    "hits_normalization": hits_normalization,
    "speed_normalization": speed_normalization,
    "position_normalization": position_normalization,
}


def get_active_metrics(has_llm_judge: bool = False) -> Dict[str, MetricDefinition]:
    """Get the active metrics based on available data."""
    active_metrics = {}
    
    # Always include retrieval metrics
    for key, metric in METRICS_CONFIG.items():
        if metric.category == MetricCategory.RETRIEVAL:
            active_metrics[key] = metric
    
    # Include LLM judge and context/position metrics only if LLM judge is available
    if has_llm_judge:
        for key, metric in METRICS_CONFIG.items():
            if metric.category in [MetricCategory.LLM_JUDGE, MetricCategory.CONTEXT, MetricCategory.POSITION]:
                active_metrics[key] = metric
    
    return active_metrics


def normalize_weights(metrics: Dict[str, MetricDefinition]) -> Dict[str, MetricDefinition]:
    """Normalize weights so they sum to 1.0."""
    total_weight = sum(metric.weight for metric in metrics.values())
    
    if total_weight == 0:
        return metrics
    
    normalized_metrics = {}
    for key, metric in metrics.items():
        normalized_metric = MetricDefinition(
            key=metric.key,
            name=metric.name,
            description=metric.description,
            category=metric.category,
            weight=metric.weight / total_weight,
            normalize_fn=metric.normalize_fn,
            higher_is_better=metric.higher_is_better
        )
        normalized_metrics[key] = normalized_metric
    
    return normalized_metrics