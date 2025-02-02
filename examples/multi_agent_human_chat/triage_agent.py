import json
from typing import Literal
from uuid import uuid4

import dspy
from eggai import Channel, Agent

human_channel = Channel("human")
agents_channel = Channel("agents")

TargetAgent = Literal["PoliciesAgent", "BillingAgent", "EscalationAgent", "TriageAgent"]

AGENT_REGISTRY = {
    "PoliciesAgent": {
        "message_type": "policy_request",
        "description": "Handles policy-related queries"
    },
    "BillingAgent": {
        "message_type": "billing_request",
        "description": "Handles billing-related queries"
    },
    "EscalationAgent": {
        "message_type": "escalation_request",
        "description": "Handles escalated queries"
    },
}


class AgentClassificationSignature(dspy.Signature):
    """
    Represents the input and output fields for the agent classification process.

    Role:
    - Acts as a Triage agent in a multi-agent insurance support system.

    Responsibilities:
    - Classifies and routes messages to appropriate target agents based on context.

    Target Agents:
    """ + "".join([f"\n- {agent}: {desc}" for agent, desc in AGENT_REGISTRY.items()]) + """

    Fallback Rules:
    - Route to TriageAgent if the target agent is not recognized.
    """

    # Input Fields
    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    # Output Fields
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )

    fall_back_reason: str = dspy.OutputField(
        desc="A kind message to the user explaining why the message was not understood."
    )

triage_classifier = dspy.ChainOfThought(signature=AgentClassificationSignature)
triage_agent = Agent(name="TriageAgent")


@triage_agent.subscribe(
    channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message"
)
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])
        meta = msg.get("meta", {})
        meta["message_id"] = msg.get("id")

        # Combine chat history
        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        # identify the agent to target based on the user chat messages
        response = triage_classifier(chat_history=conversation_string)
        target_agent = response.target_agent
        triage_to_agent_messages = [

            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            await agents_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": AGENT_REGISTRY[target_agent]["message_type"],
                    "payload": {"chat_messages": triage_to_agent_messages},
                    "meta": meta,
                }
            )
        else:
            meta["agent"] = "TriageAgent"
            await human_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": "agent_message",
                    "meta": meta,
                    "payload": response.fall_back_reason,
                }
            )
    except Exception as e:
        print("Error in TriageAgent: ", e)
