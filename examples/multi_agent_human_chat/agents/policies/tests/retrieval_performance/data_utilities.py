"""Test data for retrieval performance evaluation."""

import json
from pathlib import Path
from typing import List

from .models import RetrievalTestCase


def load_qa_pairs_from_json() -> List[RetrievalTestCase]:
    """Load test cases from filtered QA pairs JSON file."""
    json_path = Path(__file__).parent / "filtered_qa_pairs.json"

    with open(json_path, "r") as f:
        qa_pairs = json.load(f)

    test_cases = []
    for qa_pair in qa_pairs:
        test_cases.append(
            RetrievalTestCase(
                id=qa_pair["qa_pair_id"],
                question=qa_pair["question"],
                expected_answer=qa_pair["answer"],
                expected_context=qa_pair["context"],
                category=qa_pair.get("source_document", "").replace(".md", ""),
                description=f"Test case from {qa_pair.get('source_document', 'unknown')}",
            )
        )

    return test_cases


def get_retrieval_test_cases() -> List[RetrievalTestCase]:
    """Get test dataset - now loads from JSON file with context-based evaluation."""
    return load_qa_pairs_from_json()
