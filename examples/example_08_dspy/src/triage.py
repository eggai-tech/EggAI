import json
from typing import Literal
from uuid import uuid4

import dspy

from eggai import Channel, Agent

AGENT_REGISTRY = {
    "PolicyAgent": {
        "message_type": "policy_request",
        "description": (
            "Handles all policy-related inquiries. Responsibilities include fetching policy details, "
            "verifying policy status, updating policy information, and providing information on policy coverage and benefits. "
            "Users can interact with this agent by providing their policy numbers or requesting specific policy information."
        ),
    },
    "TicketingAgent": {
        "message_type": "ticketing_request",
        "description": (
            "Manages ticket creation, updates, and retrieval. This agent is responsible for logging user issues, "
            "tracking the status of existing tickets, and providing updates or resolutions to reported problems. "
            "Users can interact with this agent to report new issues or inquire about the status of their existing tickets."
        ),
    }
}

agent_registry_system_message = (
    "The target agent to handle the user request. "
    "As Triage Agent, your primary role is to triage incoming user requests and direct them to the appropriate specialized agents. "
    "You will analyze the user's message history and determine the best agent to handle the current request based on the context and content of the conversation. "
    "If the user's request is clear and falls within the scope of a specific agent, you should forward the message to that agent. "
    "If the request is ambiguous or outside the scope of known agents, you should prompt the user for more information or clarification. "
    "Your goal is to ensure that user inquiries are directed to the most suitable agent for efficient and effective resolution."
    "This is the agents registry:\n"
    f"{json.dumps(AGENT_REGISTRY, indent=4)}"
)

lm = dspy.LM('openai/gpt-4o-mini')
dspy.configure(lm=lm)

human_channel = Channel("human")
agents_channel = Channel("agents")

TargetAgent = Literal[tuple(AGENT_REGISTRY.keys())]

class ClassificationSignature(dspy.Signature):
    """Triage user messages to the correct agent."""
    chat_history: str = dspy.InputField(desc="The full chat history for context.")
    reasoning: str = dspy.OutputField(desc="Explanation of why the selected agent was chosen.")
    target_agent: TargetAgent = dspy.OutputField(desc=agent_registry_system_message)


classifier = dspy.ChainOfThought(
    signature=ClassificationSignature
)

triage_agent = Agent("TriageAgent")

@triage_agent.subscribe(channel=human_channel, filter_func=lambda msg: msg["type"] == "user_message")
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])
        meta = msg.get("meta", {})
        meta["message_id"] = msg.get("id")

        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        response = classifier(chat_history=conversation_string)

        target_agent = response.target_agent
        reasoning = response.reasoning
        triage_to_agent_messages = [{
            "role": "user",
            "content": f"{conversation_string}\nReasoning: {reasoning}\n{target_agent}: ",
        }]

        print(f"Target Agent: {target_agent}")

        if target_agent in AGENT_REGISTRY and target_agent != "TriageAgent":
            await agents_channel.publish({
                "type": AGENT_REGISTRY[target_agent]["message_type"],
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
                "meta": meta,
            })
        else:
            meta["agent"] = "TriageAgent"
            await human_channel.publish({
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?",
            })
    except Exception as e:
        print("Error in DSPy Triage Agent: ", e)