import json
from uuid import uuid4

import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent

policies_agent = Agent(name="PoliciesAgent")

agents_channel = Channel("agents")
human_channel = Channel("human")

policies_database = [
    {"policy_number": "A12345", "name": "John Doe", "coverage_details": "Comprehensive", "premium_amount": 500,
     "due_date": "2025-01-01"},
    {"policy_number": "B67890", "name": "Jane Smith", "coverage_details": "Liability", "premium_amount": 300,
     "due_date": "2025-02-01"},
    {"policy_number": "C24680", "name": "Alice Johnson", "coverage_details": "Collision", "premium_amount": 400,
     "due_date": "2025-03-01"},
]

def get_policy_details(policy_number: str) -> str:
    """
    Retrieves detailed information for a given policy number.
    Returns a JSON-formatted string if the policy is found, or "Policy not found." otherwise.
    """
    print(f"[Tool] Retrieving policy details for policy number: {policy_number}")
    for policy in policies_database:
        if policy["policy_number"] == policy_number.strip():
            return json.dumps(policy)
    return "Policy not found."


class PolicyAgentSignature(dspy.Signature):
    """
    This signature defines the input and output for processing policy inquiries
    using a simple ReACT loop.

    Role:
    - You are the Policy Agent for an insurance company. Your job is to help users
      with inquiries about insurance policies (coverage details, premiums, etc.).
    - If the necessary policy details (e.g. a policy number) are provided, use a tool
      to retrieve policy information.
    - If not, ask for the missing information.
    - Maintain a polite, concise, and helpful tone.

    Input Fields:
    - chat_history: A string containing the full conversation history for context.

    Output Fields:
    - final_response: The final answer to be sent to the user.
    - action: A directive indicating a tool action to take (e.g., "get_policy_details").
              If empty, no tool call is needed.
    - action_input: The input required for the action (e.g., the policy number).
    """
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Final response message to the user.")

policies_react = dspy.ReAct(PolicyAgentSignature, tools=[get_policy_details])

@policies_agent.subscribe(
    channel=agents_channel,
    filter_func=lambda msg: msg["type"] == "policy_request"
)
async def handle_policy_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"
        response = policies_react(chat_history=conversation_string)
        final_response = response.final_response
        meta = msg.get("meta", {})
        meta["agent"] = "PoliciesAgent"
        await human_channel.publish({
            "id": str(uuid4()),
            "type": "agent_message",
            "meta": meta,
            "payload": final_response,
        })
    except Exception as e:
        print(f"Error in PoliciesAgent: {e}")


if __name__ == "__main__":
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=language_model)

    print(policies_react(chat_history="""
    User: I need information about my policy.
    PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?
    User: My policy number is A12345
    """).final_response)
