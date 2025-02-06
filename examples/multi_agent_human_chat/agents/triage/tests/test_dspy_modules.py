import pytest
from ..dspy_modules.evaluation.evaluate import run_evaluation_v1

@pytest.mark.asyncio
async def test_dspy_modules():
    score = run_evaluation_v1()
    assert score > 0.6, "Evaluation score is below threshold."