import dspy

language_model = dspy.LM('openai/gpt-4o-mini')
dspy.configure(lm=language_model)