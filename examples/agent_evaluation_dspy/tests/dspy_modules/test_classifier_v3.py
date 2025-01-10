from os import path

import pytest
from dotenv import load_dotenv

from src.dspy_modules.classifier_v3 import optimize, load
from tests.dspy_modules.utils import load_data, run_evaluation, generate_report


@pytest.mark.asyncio
def test_classifier_v3():
    load_dotenv()
    test_dataset = load_data(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "datasets", "triage-testing.json")))

    training_dataset = load_data(
        path.abspath(path.join(path.dirname(__file__), "..", "..", "datasets", "triage-training.json")))
    REWRITE_OPTIMIZATION = False
    optimize(training_dataset, overwrite=REWRITE_OPTIMIZATION)
    classifier_v3 = load()
    score_v3, results_v3 = run_evaluation(classifier_v3, test_dataset)
    generate_report(results_v3, "classifier_v3")
