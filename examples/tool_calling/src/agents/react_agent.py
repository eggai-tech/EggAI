from eggai import Channel, Agent
from eggai.schemas import Message

from dspy_modules.react_module import react_module

agents_channel = Channel("agents")

react_agent = Agent("AnswersAgent")


@react_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "question"
)
async def handle_question(msg: Message):
    question = msg.data.get("message")

    prediction = react_module(question=question)

    answer_message = Message(
        type="answer",
        source="react_agent",
        data={
            "answer": prediction.answer,
            "numeric_answer": prediction.numeric_answer,
            "reasoning": prediction.reasoning,
        },
    )
    await agents_channel.publish(answer_message)
