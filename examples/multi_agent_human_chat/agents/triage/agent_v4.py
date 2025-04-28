import dotenv
import mlflow
import numpy as np
from eggai import Channel, Agent

from mlflow_.utils import find_artifact
from src.baseline_model.fewshot_classifier import FewshotClassifier

human_channel = Channel("human")
agents_channel = Channel("agents")

triage_agent_v4 = Agent("TriageAgent")

dotenv.load_dotenv()

classifier_v4 = FewshotClassifier()
classifier_v4.load(mlflow.artifacts.download_artifacts(find_artifact("fewshot_classifier_n_200.pkl")))


@triage_agent_v4.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message_v4(msg):
    """
    Handles user messages and routes them to the appropriate target agent.
    """
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", "")

        labels = {'BillingAgent': 0, 'PolicyAgent': 1, 'ClaimsAgent': 2, 'EscalationAgent': 3, 'ChattyAgent': 4}
        pred_matrix = classifier_v4([chat_messages])[0]

        best_label = np.argmax(pred_matrix)
        best_target_agent = [k for k, v in labels.items() if v == best_label][0]

        return {
            "target_agent": best_target_agent,
            "cost": 0,
        }
    except Exception as e:
        print("Error in Triage Agent: ", e)


if __name__ == "__main__":
    async def main():
        test_event = {
            "type": "user_message",
            "payload": {
                "chat_messages": "User: Hello, I need help with my insurance claim.",
            },
        }
        r = await handle_user_message_v4(test_event)
        print(r)


    import asyncio

    asyncio.run(main())
