import pytest
from dotenv import load_dotenv

from ..src.dspy_modules.triage_module import triage_module as classifier_v2
from .utilities import load_data, run_evaluation


def test_intent_classifier():
    load_dotenv()
    test_dataset = load_data("triage-testing")
    score, results = run_evaluation(classifier_v2, test_dataset)
    
    # Track failures for debugging
    failures = []
    for result in results:
        example, prediction, passed = result
        if not passed:
            failures.append(f"Chat History: {example.chat_history} - Expected {example.target_agent}, got {prediction.target_agent}")
    
    # Print failures for debugging purposes
    if failures:
        print(f"\nMisclassified examples ({len(failures)} out of {len(results)}):")
        for failure in failures:
            print(f"  - {failure}")
    
    # The test should pass if we achieve > 90% accuracy
    # This allows for some misclassifications which is realistic for ML models
    assert score > 0.9, f"Success rate {score:.2f} is not greater than 90%."
