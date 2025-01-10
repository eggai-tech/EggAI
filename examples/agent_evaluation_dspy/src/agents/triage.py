from eggai import Channel, Agent
from examples.agent_evaluation_dspy.src.dspy_modules.classifier_v3 import load

human_channel = Channel("human")
agents_channel = Channel("agents")

triage_agent = Agent("TriageAgent")


@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message(msg):
    """
    Handles user messages and routes them to the appropriate target agent.
    """
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", "")
        classifier = load()
        response = classifier(chat_history=chat_messages)
        target_agent = response.target_agent

        await agents_channel.publish({"target": target_agent, "payload": payload})
    except Exception as e:
        print("Error in Triage Agent: ", e)
