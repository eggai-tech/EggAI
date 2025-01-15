from eggai import Channel, Agent

from src.agents.guardrail import guard
from src.dspy_modules.wiki_qa import wiki_qa

agents_channel = Channel("agents")

answers_agent = Agent("AnswersAgent")


@answers_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "question"
)
async def handle_question(msg):
    question = msg["payload"]

    # Input guarding
    valid_question = guard(question)
    if valid_question is None:
        await agents_channel.publish({
            "type": "error",
            "payload": {
                "error_code": "INPUT_GUARDRAIL",
                "error_message": "Guard stopped the question"
            }
        })
        print("Question:", question)
        print("Answer:", None)
        print("Error: INPUT_GUARDRAIL")
        return

    prediction = wiki_qa(question=valid_question)

    # Output guarding
    valid_answer = guard(prediction.answer)
    if valid_answer is None:
        await agents_channel.publish({
            "type": "error",
            "payload": {
                "error_code": "OUTPUT_GUARDRAIL",
                "error_message": "Guard stopped the answer"
            }
        })
        print("Question:", valid_question)
        print("Answer:", prediction.answer)
        print("Error: OUTPUT_GUARDRAIL")
        return

    print("Question:", valid_question)
    print("Answer:", valid_answer)
    await agents_channel.publish({
        "type": "answer",
        "payload": {
            "question": valid_question,
            "answer": valid_answer
        }
    })
