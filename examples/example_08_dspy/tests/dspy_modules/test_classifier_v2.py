from os import path

import pytest
from dotenv import load_dotenv

from examples.example_08_dspy.src.dspy_modules.classifier_v2 import classifier as classifier_v2
from examples.example_08_dspy.tests.dspy_modules.utils import load_data, run_evaluation, generate_report


@pytest.mark.asyncio
def test_classifier_v2():
    load_dotenv()
    test_dataset = load_data(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "datasets", "triage-testing.json")))
    score_v2, results_v2 = run_evaluation(classifier_v2, test_dataset)
    generate_report(results_v2, "classifier_v2")
