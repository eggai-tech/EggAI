from os import path

import pytest
from dotenv import load_dotenv

from examples.agent_evaluation_dspy.src.dspy_modules.classifier_v1 import classifier as classifier_v1
from examples.agent_evaluation_dspy.tests.dspy_modules.utils import load_data, run_evaluation, generate_report


@pytest.mark.asyncio
def test_classifiers():
    load_dotenv()
    test_dataset = load_data(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "datasets", "triage-testing.json")))
    score_v1, results_v1 = run_evaluation(classifier_v1, test_dataset)
    generate_report(results_v1, "classifier_v1")
