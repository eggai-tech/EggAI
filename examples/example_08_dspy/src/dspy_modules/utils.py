from examples.example_08_dspy.src.dspy_modules.lm import language_model


def run_and_calculate_costs(program, chat_history):
    program(chat_history=chat_history)
    last_history = language_model.history[-1]
    cost = last_history['cost']
    if cost:
        print(f"Cost: {cost:.10f}$")
        print(f"Run it {1 / cost:.0f} times to reach one dollar.")
    else:
        print("No cost. (cached)")
