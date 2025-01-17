import pytest

from src.dspy_modules.react_module import react_module, transactions_list

EIFFEL_TOWER = 1889
EMPIRE_STATE_BUILDING = 1931


@pytest.mark.asyncio
async def test_eiffel_plus_empire():
    pred = react_module(
        question="Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building.")
    assert pred.numeric_answer == EIFFEL_TOWER + EMPIRE_STATE_BUILDING


@pytest.mark.asyncio
async def test_handle_balance():
    pred = react_module(question="What is my balance until 2022-01-03 included?", k=3)

    expected_balance = 0
    for transaction in transactions_list:
        if transaction["date"] <= "2022-01-03":
            expected_balance += transaction["amount"] if transaction["type"] == "credit" else -transaction["amount"]

    assert pred.numeric_answer == expected_balance


@pytest.mark.asyncio
async def test_handle_balance_plus_eiffel():
    pred = react_module(
        question="What is my balance until 2022-01-03 included summed with the year of construction of the Eiffel Tower?")
    expected_balance = 0
    for transaction in transactions_list:
        if transaction["date"] <= "2022-01-03":
            expected_balance += transaction["amount"] if transaction["type"] == "credit" else -transaction["amount"]

    assert pred.numeric_answer == expected_balance + EIFFEL_TOWER
