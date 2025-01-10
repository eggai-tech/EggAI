from os import path

import pytest
from dotenv import load_dotenv

from ..src.dspy_modules.classifier_v2 import classifier as classifier_v2
from .utilities import load_data, run_evaluation, generate_report


@pytest.mark.asyncio
def test_classifier_v2():
    load_dotenv()
    test_dataset = load_data("triage-testing")
    score_v2, results_v2 = run_evaluation(classifier_v2, test_dataset)
    generate_report(results_v2, "classifier_v2")
