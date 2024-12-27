import json

from lite_llm_agent import LiteLlmAgent
from shared import agents_channel

policy_agent = LiteLlmAgent(
    name="PolicyAgent",
    system_message=(
        "You are the Policy Agent for an insurance company. "
        "Your job is to answer questions about policies: coverage details, premiums, and policy changes. "
        "\n\n"
        "Key Instructions:\n"
        "1. Always identify yourself as the 'Policy Agent.' Never call yourself the 'Claims Agent' or 'Escalation Agent.'\n"
        "2. If a user needs policy details, request their policy number (if not already provided). "
        "   If the user does not have a policy number, ask for their full name.\n"
        "3. Use the tool 'get_policy_details' to fetch policy information, which includes:\n"
        "   - Policyholder's name\n"
        "   - Policy type\n"
        "   - Coverage details\n"
        "   - Premium amount\n"
        "   - Premium due date\n"
        "4. If you cannot find the policy by either policy number or policyholder name, respond with 'Policy not found.' "
        "   and ask for clarification.\n"
        "5. If the question goes beyond policy details (e.g., filing a claim), forward it to the TriageAgent.\n"
        "\n"
        "Remember: You are the Policy Agent, and you handle policy-related inquiries. Stay within your scope, "
        "and always be polite, concise, and helpful."
    ),
    model="gpt-3.5-turbo-1106"
)

policies_database = [
    {"policy_number": "A12345", "name": "John Doe", "coverage_details": "Comprehensive", "premium_amount": 500, "due_date": "2025-01-01"},
    {"policy_number": "B67890", "name": "Jane Smith", "coverage_details": "Liability", "premium_amount": 300, "due_date": "2025-02-01"},
    {"policy_number": "C24680", "name": "Alice Johnson", "coverage_details": "Collision", "premium_amount": 400, "due_date": "2025-03-01"},
]

@policy_agent.tool()
async def get_policy_details(policy_number: str):
    """
    Get policy details for a given policy number.

    :param policy_number: The policy number to fetch details for.

    :return: The policy details as a JSON object.
    """
    print(f"[TOOL CALL] get_policy_details: {policy_number}")
    for policy in policies_database:
        if policy["policy_number"] == policy_number:
            return json.dumps(policy)

    return "Policy not found."


@policy_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "policy_request")
async def handle_policy_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await policy_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "PolicyAgent"})

        await agents_channel.publish({
            "type": "response",
            "agent": "PolicyAgent",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        print(f"[red]Error in PolicyAgent: {e}[/red]")