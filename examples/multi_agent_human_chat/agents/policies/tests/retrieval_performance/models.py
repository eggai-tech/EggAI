"""Data models for retrieval performance testing."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RetrievalTestCase(BaseModel):
    """Test case for retrieval performance evaluation."""
    id: str
    question: str
    expected_answer: str
    expected_chunk_ids: List[str]
    category: Optional[str] = None
    description: str = ""


@dataclass
class ParameterCombination:
    """Test parameter combination."""
    test_case_id: str
    search_type: str
    max_hits: int

    def to_experiment_name(self) -> str:
        return f"retrieval_{self.test_case_id}_{self.search_type}_hits{self.max_hits}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "search_type": self.search_type,
            "max_hits": self.max_hits,
        }


@dataclass
class RetrievalResult:
    """Stage 1 query results."""
    combination: ParameterCombination
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_time_ms: float
    total_hits: int
    error: Optional[str] = None


@dataclass
class EvaluationResult:
    """Stage 2 LLM evaluation results."""
    combination: ParameterCombination
    retrieval_quality_score: float
    completeness_score: float
    relevance_score: float
    reasoning: str
    judgment: bool
    evaluation_time_ms: float
    error: Optional[str] = None


@dataclass
class RetrievalTestConfiguration:
    """Test configuration."""
    search_types: List[str] = None
    max_hits_values: List[int] = None
    parallel_queries: bool = True
    parallel_evaluations: bool = True
    max_query_workers: int = 5
    max_eval_workers: int = 3

    def __post_init__(self):
        if self.search_types is None:
            self.search_types = ["hybrid", "keyword", "vector"]
        if self.max_hits_values is None:
            self.max_hits_values = [1, 5, 10]