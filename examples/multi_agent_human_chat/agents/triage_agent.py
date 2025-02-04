from typing import Literal, Optional
from uuid import uuid4

import dspy
from eggai import Channel, Agent

human_channel = Channel("human")
agents_channel = Channel("agents")

TargetAgent = Literal["PoliciesAgent", "BillingAgent", "EscalationAgent", "TriageAgent"]

AGENT_REGISTRY = {
    "PoliciesAgent": {
        "message_type": "policy_request",
        "description": "Handles policy-related queries",
    },
    "BillingAgent": {
        "message_type": "billing_request",
        "description": "Handles billing-related queries",
    },
    "EscalationAgent": {
        "message_type": "escalation_request",
        "description": "Handles escalated queries",
    },
}


class AgentClassificationSignature(dspy.Signature):
    (
        """
    Represents the input and output fields for the agent classification process.

    Role:
    - Acts as a Triage agent in a multi-agent insurance support system.

    Responsibilities:
    - Classifies and routes messages to appropriate target agents based on context.
    - Handles small talk or casual greetings directly.

    Target Agents:
    """
        + "".join([f"\n- {agent}: {desc}" for agent, desc in AGENT_REGISTRY.items()])
        + """

    Smalltalk Rules:
    - Route to TriageAgent if the target agent is not recognized.
    - Respond to small talk or casual greetings with a friendly message, such as: 'Hello! 👋 How can I assist you with your insurance today? Feel free to ask about policies, billing, claims, or anything else!'

    Fallback Rules:
    - Route to TriageAgent if the target agent is not recognized.
    - Provide helpful guidance if the message intent is not recognized.
    """
    )

    # Input Fields
    chat_history: str = dspy.InputField(
        desc="Full chat history providing context for the classification process."
    )

    # Output Fields
    target_agent: TargetAgent = dspy.OutputField(
        desc="Target agent classified for triage based on context and rules."
    )

    small_talk_message: Optional[str] = dspy.OutputField(
        desc="A friendly response to small talk or casual greetings if small talk intent is identified."
    )

    fall_back_message: Optional[str] = dspy.OutputField(
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
            message_to_send = response.small_talk_message or response.fall_back_message or ""
            meta["agent"] = "TriageAgent"
            await human_channel.publish(
                {
                    "id": str(uuid4()),
                    "type": "agent_message",
                    "meta": meta,
                    "payload": message_to_send,
                }
            )
    except Exception as e:
        print("Error in TriageAgent: ", e)
