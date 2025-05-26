import pytest

from src.dspy_modules.react_module import react_module


@pytest.mark.asyncio
async def test_train_catch_up():
    expected_answer = 5
    pred = react_module(
        question="An ICE train of Deutsche Bahn travels from Cologne to Berlin at a speed of 200 km/h. A second ICE departs one hour later on the same route, but at a speed of 250 km/h. When will the second train catch up with the first train?"
    )
    assert pred.numeric_answer == expected_answer

@pytest.mark.asyncio
async def test_multiplication():
    expected_answer = 670592745
    pred = react_module(
        question="what's the result of 12345 multiplied by 54321?"
    )
    assert pred.numeric_answer == expected_answer
