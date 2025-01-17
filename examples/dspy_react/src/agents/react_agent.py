from eggai import Channel, Agent

from src.dspy_modules.react_module import react_module

agents_channel = Channel("agents")

react_agent = Agent("AnswersAgent")


@react_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "question"
)
async def handle_question(msg):
    question = msg["payload"]

    prediction = react_module(question=question)
    answer = prediction.answer

    print("Question:", question)
    print("Answer:", answer)
    await agents_channel.publish({
        "type": "answer",
        "payload": {
            "question": question,
            "answer": answer
        }
    })
