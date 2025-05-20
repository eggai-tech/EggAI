import dspy
from src.config import Settings


settings = Settings()
language_model = dspy.LM(
    model=settings.language_model,
    api_base=settings.language_model_api_base,
    cache=settings.cache_enabled,
)
dspy.configure(lm=language_model)


def execute_python_code(code: str) -> float:
    """
    Evaluates a python code and returns the result.
    """
    try:
        result = dspy.PythonInterpreter({}, import_white_list=["sympy"]).execute(code)
    except Exception as e:
        print(f"Error evaluating code: {e}")
        return None
    return result


react_module = dspy.ReAct(
    "question -> answer, numeric_answer: float", tools=[execute_python_code]
)

if __name__ == "__main__":
    prediction = react_module(
        question="what's the result of 12345 multiplied by 54321?"
    )
    print(f"Answer: {prediction.answer}")
    print(f"Reasoning: {prediction.reasoning}")
    print(f"Numeric answer: {prediction.numeric_answer}")
    print(f"Trajectory: {prediction.trajectory}")
