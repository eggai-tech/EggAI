from eggai import Channel, Agent
from examples.example_08_dspy.src.classifiers.v1 import optimized_classifier

human_channel = Channel("human")
agents_channel = Channel("agents")


triage_agent = Agent("TriageAgent")


@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", "")
        meta = msg.get("meta", {})
        meta["message_id"] = msg.get("id")
        conversation_string = ""

        response = optimized_classifier(chat_history=conversation_string)

        meta["confidence"] = response.confidence
        meta["reasoning"] = response.reasoning

        target_agent = response.target_agent
        reasoning = response.reasoning
        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string}\nReasoning: {reasoning}\n{target_agent}: ",
            }
        ]

        await agents_channel.publish(
            {
                "type": "message_to_" + target_agent,
                "payload": {"chat_messages": triage_to_agent_messages},
                "meta": meta,
            }
        )
    except Exception as e:
        print("Error in DSPy Triage Agent: ", e)
