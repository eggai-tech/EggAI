import dspy
from dotenv import load_dotenv

transactions_list = [
    {"description": "Initial Balance", "type": "credit", "amount": 5000.0, "date": "2022-01-01"},
    {"description": "Taxes", "type": "credit", "amount": 100.0, "date": "2022-01-02"},
    {"description": "Salary", "type": "debit", "amount": 500.0, "date": "2022-01-03"},
    {"description": "Coffee Shop", "type": "debit", "amount": 15.0, "date": "2022-01-05"},
    {"description": "Utility Bill", "type": "debit", "amount": 120.0, "date": "2022-01-08"},
    {"description": "Freelance Work", "type": "credit", "amount": 300.0, "date": "2022-01-15"},
    {"description": "Dinner Out", "type": "debit", "amount": 80.0, "date": "2022-01-20"},
    {"description": "Book Purchase", "type": "debit", "amount": 25.0, "date": "2022-01-25"},
    {"description": "Gift", "type": "credit", "amount": 50.0, "date": "2022-01-28"},
    {"description": "Car Maintenance", "type": "debit", "amount": 250.0, "date": "2022-02-02"},
    {"description": "Rent Payment", "type": "debit", "amount": 1000.0, "date": "2022-02-05"},
    {"description": "Gym Membership", "type": "debit", "amount": 45.0, "date": "2022-02-10"},
    {"description": "Interest Payment", "type": "credit", "amount": 20.0, "date": "2022-02-14"},
    {"description": "Movie Night", "type": "debit", "amount": 30.0, "date": "2022-02-18"},
    {"description": "Online Course", "type": "debit", "amount": 150.0, "date": "2022-02-22"},
    {"description": "Electricity Bill", "type": "debit", "amount": 95.0, "date": "2022-02-25"},
    {"description": "Savings Deposit", "type": "credit", "amount": 200.0, "date": "2022-03-01"}
]


def evaluate_math(expression: str) -> float:
    return dspy.PythonInterpreter({}).execute(expression)


def search_wikipedia(query: str):
    results = dspy.ColBERTv2(url='http://20.102.90.50:2017/wiki17_abstracts')(query, k=3)
    return [x['text'] for x in results]


def list_transactions(end_date_yyyy_mm_dd: str = '9999-12-31'):
    return [x for x in transactions_list if x["date"] <= end_date_yyyy_mm_dd]


react_module = dspy.ReAct("question -> answer, numeric_answer: float",
                          tools=[evaluate_math, search_wikipedia, list_transactions])

if __name__ == "__main__":
    load_dotenv()
    EIFFEL_TOWER = 1889
    EMPIRE_STATE_BUILDING = 1931
    assert react_module(
        question="Give me the year of construction of the Eiffel Tower summed with the year of construction of the Empire State Building.").numeric_answer == EIFFEL_TOWER + EMPIRE_STATE_BUILDING
    assert react_module(
        question="What is my balance until 2022-01-03 included?").numeric_answer == 5000.0 + 100.0 - 500.0
    assert react_module(
        question="What is my balance until 2022-01-03 included summed with the year of construction of the Eiffel Tower?").numeric_answer == 5000.0 + 100.0 - 500.0 + EIFFEL_TOWER
