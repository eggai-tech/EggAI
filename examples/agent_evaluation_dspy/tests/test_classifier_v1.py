from os import path

import pytest
from dotenv import load_dotenv


from ..src.dspy_modules.classifier_v1 import classifier as classifier_v1
from .utilities import load_data, run_evaluation, generate_report


@pytest.mark.asyncio
def test_classifier_v1():
    load_dotenv()
    test_dataset = load_data("triage-testing")
    score_v1, results_v1 = run_evaluation(classifier_v1, test_dataset)
    generate_report(results_v1, "classifier_v1")
