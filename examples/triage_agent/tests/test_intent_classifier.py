import pytest
from dotenv import load_dotenv

from ..src.dspy_modules.triage_module import triage_module as classifier_v2
from .utilities import load_data, run_evaluation


@pytest.mark.asyncio
def test_intent_classifier():
    load_dotenv()
    test_dataset = load_data("triage-testing")
    score, results = run_evaluation(classifier_v2, test_dataset)
    for result in results:
        example, prediction, passed = result
        assert passed, f"Chat History: {example.chat_history} failed. Reasoning: {prediction.reasoning}. Expected {example.target_agent}, got {prediction.target_agent}."
    assert score > 0.9, f"Success rate {score:.2f}% is not greater than 90%."
