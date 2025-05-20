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
    return dspy.PythonInterpreter({}, import_white_list=["sympy"]).execute(code)


react_module = dspy.ReAct(
    "question -> answer, numeric_answer: float", tools=[execute_python_code]
)

if __name__ == "__main__":
    prediction = react_module(
        question="An ICE train of Deutsche Bahn travels from Cologne to Berlin at a speed of 200 km/h. A second ICE departs one hour later on the same route, but at a speed of 250 km/h. When will the second train catch up with the first train?"
    )
    print(f"Answer: {prediction.answer}")
    print(f"Reasoning: {prediction.reasoning}")
    print(f"Numeric answer: {prediction.numeric_answer}")
    print(f"Trajectory: {prediction.trajectory}")
