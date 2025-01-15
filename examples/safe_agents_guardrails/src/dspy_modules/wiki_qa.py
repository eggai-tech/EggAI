import dspy
from dotenv import load_dotenv

from src.dspy_modules.lm import language_model


def search_wikipedia(query: str):
    results = dspy.ColBERTv2(url='http://20.102.90.50:2017/wiki17_abstracts')(query, k=3)
    return [x['text'] for x in results]

wiki_qa = dspy.ReAct("question -> answer", tools=[search_wikipedia])
