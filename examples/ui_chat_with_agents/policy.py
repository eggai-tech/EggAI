import json
from uuid import uuid4

from sdk.eggai import Channel
from lite_llm_agent import LiteLlmAgent

agents_channel = Channel("agents")
human_channel = Channel("human")

policy_agent = LiteLlmAgent(
    name="PolicyAgent",
    system_message=(
        "You are the Policy Agent for an insurance company. Your primary responsibility is to assist users with inquiries related to insurance policies, including coverage details, premiums, and policy modifications.\n\n"
        "Key Instructions:\n"
        "1. **Identification:** Always identify yourself as the 'Policy Agent.' Do not refer to yourself as the 'Claims Agent' or 'Escalation Agent.'\n"
        "2. **Policy Verification:**\n"
        "   - If a user requests policy details, ask for their **policy number** if it hasn't been provided.\n"
        "   - If the user does not have their policy number, request their **full name** to locate the policy.\n"
        "3. **Policy Lookup:**\n"
        "   - Use the provided policy number or policyholder name to retrieve policy information from the database.\n"
        "   - If the policy is not found, respond with 'Policy not found.' and prompt the user to verify their details.\n"
        "4. **Scope Limitation:**\n"
        "   - If a user’s query extends beyond policy details (e.g., filing a claim, policy cancellation), inform them that their request will be forwarded to the **TriageAgent** for further assistance.\n"
        "5. **Communication Style:**\n"
        "   - Maintain a **polite**, **concise**, and **helpful** tone in all responses.\n"
        "   - Ensure clarity and avoid using jargon or complex terminology.\n\n"
        "Guidelines:\n"
        "• Stay within the scope of handling policy-related inquiries.\n"
        "• Always strive to provide accurate and prompt assistance.\n"
    ),
    model="openai/gpt-4"
)

policies_database = [
    {"policy_number": "A12345", "name": "John Doe", "coverage_details": "Comprehensive", "premium_amount": 500, "due_date": "2025-01-01"},
    {"policy_number": "B67890", "name": "Jane Smith", "coverage_details": "Liability", "premium_amount": 300, "due_date": "2025-02-01"},
    {"policy_number": "C24680", "name": "Alice Johnson", "coverage_details": "Collision", "premium_amount": 400, "due_date": "2025-03-01"},
]

@policy_agent.tool()
async def get_policy_details(policy_number: str) -> str:
    """
    Retrieve detailed information for a specific insurance policy.

    **Parameters:**
    - `policy_number` (str): The unique identifier of the insurance policy to be retrieved.

    **Returns:**
    - `str`: A JSON-formatted string containing the following fields if the policy is found:
        - `policy_number` (str): The unique policy identifier.
        - `name` (str): The full name of the policyholder.
        - `coverage_details` (str): Description of the coverage type (e.g., Comprehensive, Liability, Collision).
        - `premium_amount` (float): The premium amount in USD.
        - `due_date` (str): The next premium due date in YYYY-MM-DD format.
      If the policy is not found, returns the string `"Policy not found."`

    **Example:**
    ```json
    {
        "policy_number": "A12345",
        "name": "John Doe",
        "coverage_details": "Comprehensive",
        "premium_amount": 500,
        "due_date": "2025-01-01"
    }
    ```

    **Possible Errors:**
    - If `policy_number` is not provided or is in an incorrect format, the function will return `"Invalid policy number provided."`

    :param policy_number: The unique identifier of the insurance policy to be retrieved.
    """
    print(f"[Tool] Retrieving policy details for policy number: {policy_number}")
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
        meta = msg.get("meta", {})
        meta["agent"] = "PolicyAgent"
        await human_channel.publish({
            "id": str(uuid4()),
            "type": "agent_message",
            "meta": meta,
            "payload": reply,
        })
    except Exception as e:
        print(f"Error in PolicyAgent: {e}")