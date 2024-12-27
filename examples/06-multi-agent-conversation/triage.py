import json

from lite_llm_agent import LiteLlmAgent
from shared import AGENT_REGISTRY, agents_channel, humans_channel
from memory import messages_history_memory


def build_triage_system_prompt(agent_registry):
    guidelines = "Guidelines:\n"
    for agent_name, agent_info in agent_registry.items():
        if agent_name != "EscalationAgent":
            keywords = ", ".join(agent_info.get("keywords", []))
            guidelines += (
                f"• If the user is asking about {keywords}, target = '{agent_name}'.\n"
            )
    guidelines += (
        "• If you cannot determine the category or if the request is out of scope, target = 'EscalationAgent'.\n"
        "• If the request is unclear but appears to require human support, forward to EscalationAgent.\n"
    )
    guidelines += (
        "Respond only with a JSON object indicating the target agent. Do not include any additional text or explanation.\n"
        "Example: {\"target\": \"ClaimsAgent\"}\n"
        "Remember: You must never provide any text other than the JSON object with the key 'target'."
    )

    system_prompt = f"""
You are an advanced Triage Assistant for a multi-agent system. Your primary responsibility is to analyze the user’s message and determine the most appropriate agent to handle the request.

{guidelines}
"""
    return system_prompt

triage_agent = LiteLlmAgent(
    name="TriageAgent",
    system_message=build_triage_system_prompt(AGENT_REGISTRY),
    model="gpt-3.5-turbo-1106"
)


@triage_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "user_message")
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])

        # identify the agent to target based on the user chat messages
        response = await triage_agent.completion(messages=[{
            "role": "user",
            "content": json.dumps(chat_messages),
        }])

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            await agents_channel.publish({
                "type": "response",
                "agent": "TriageAgent",
                "payload": "There was an error processing your request. Please try again."
            })
            return

        target_agent = reply.get("target")


        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        triage_to_agent_messages = [{
            "role": "user",
            "content": f"You are {target_agent}, please continue the conversation. \n\n{conversation_string}",
        }]

        if target_agent == "ClaimsAgent":
            await agents_channel.publish({
                "type": "claims_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        elif target_agent == "PolicyAgent":
            await agents_channel.publish({
                "type": "policy_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        elif target_agent == "EscalationAgent":
            await agents_channel.publish({
                "type": "escalation_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        else:
            await agents_channel.publish({
                "type": "response",
                "agent": "TriageAgent",
                "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?",
            })
    except Exception as e:
        print("Error in TriageAgent: ", e)


@triage_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "response")
async def triage_write_memory(msg):
    try:
        chat_messages = msg.get("payload", {}).get("chat_messages", [])
        messages_history_memory.clear()
        messages_history_memory.extend(chat_messages)
    except Exception as e:
        print(f"Error in TriageAgent: {e}")

