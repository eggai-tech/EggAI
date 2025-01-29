import json
from uuid import uuid4

from eggai import Channel
from lite_llm_agent import LiteLlmAgent

human_channel = Channel("human")
agents_channel = Channel("agents")

AGENT_REGISTRY = {
    "PolicyAgent": {
        "message_type": "policy_request",
        "keywords": [
            "policy details",
            "coverage",
            "premium",
            "modify policy",
            "policy number",
        ],
    },
    "BillingAgent": {
        "message_type": "billing_request",
        "keywords": ["billing", "invoice", "payment", "premium due", "billing issue"],
    },
    "EscalationAgent": {
        "message_type": "escalation_request",
        "keywords": ["file a claim", "claim status", "accident", "incident"],
    },
}


def build_triage_system_prompt(agent_registry):
    guidelines = "Guidelines:\n"
    for agent_name, agent_info in agent_registry.items():
        keywords = ", ".join(agent_info.get("keywords", []))
        guidelines += (
            f"• If the user is asking about {keywords}, target = '{agent_name}'.\n"
        )
    guidelines += "• If the user is asking about claims-related topics such as 'file a claim', 'claim status', 'accident', or 'incident', target = 'EscalationAgent'.\n"
    guidelines += (
        "Respond only with a JSON object indicating the target agent. Do not include any additional text or explanation.\n"
        'Example: {"target": "PolicyAgent"}\n'
        "Remember: You must never provide any text other than the JSON object with the key 'target'."
    )

    system_prompt = f"""
You are an advanced Triage Assistant for a multi-agent insurance support system. Your primary responsibility is to analyze the user’s message and determine the most appropriate agent to handle the request.

{guidelines}
"""
    return system_prompt


triage_agent = LiteLlmAgent(
    name="TriageAgent",
    system_message=build_triage_system_prompt(AGENT_REGISTRY),
    model="openai/gpt-4o-mini",
)


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
        response = await triage_agent.completion(
            messages=[
                {
                    "role": "user",
                    "content": f"Based on this conversation history: {conversation_string}, determine the target agent as a JSON object.",
                }
            ]
        )

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            await agents_channel.publish(
                {
                    "type": "response",
                    "agent": "TriageAgent",
                    "payload": "There was an error processing your request. Please try again.",
                }
            )
            return

        target_agent = reply.get("target")

        triage_to_agent_messages = [
            {
                "role": "user",
                "content": f"{conversation_string} \n{target_agent}: ",
            }
        ]

        if target_agent in AGENT_REGISTRY:
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
                    "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?",
                }
            )
    except Exception as e:
        print("Error in TriageAgent: ", e)
