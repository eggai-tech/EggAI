import json
from uuid import uuid4
import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent

billing_agent = Agent(name="BillingAgent")

agents_channel = Channel("agents")
human_channel = Channel("human")


class BillingAgentSignature(dspy.Signature):
    """
    You are the Billing Agent for an insurance company.

    ROLE:
      - Assist customers with billing-related inquiries such as due amounts, billing cycles, payment statuses, etc.
      - Retrieve or update billing information as needed.
      - Provide polite, concise, and helpful answers.

    TOOLS:
      - get_billing_info(policy_number): Retrieves billing information (amount due, due date, payment status, etc.).
      - update_billing_info(policy_number, field, new_value): Updates a particular field in the billing record.

    RESPONSE FORMAT:
      - Provide a concise, courteous message summarizing relevant billing info or acknowledging an update.
        For instance:
          "Your next payment of $100 is due on 2025-02-01, and your current status is 'Paid'."

    GUIDELINES:
      - Maintain a polite, professional tone.
      - Only use the tools if necessary (e.g., if the user provides a policy number and requests an update or info).
      - If a policy number is missing or unclear, politely ask for it.
      - Avoid speculation or divulging irrelevant details.

    Input Fields:
      - chat_history: A string containing the full conversation thus far.

    Output Fields:
      - final_response: The final text answer to the user regarding their billing inquiry.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


billing_database = [
    {
        "policy_number": "A12345",
        "billing_cycle": "Monthly",
        "amount_due": 120.0,
        "due_date": "2025-02-01",
        "status": "Paid",
    },
    {
        "policy_number": "B67890",
        "billing_cycle": "Quarterly",
        "amount_due": 300.0,
        "due_date": "2025-03-15",
        "status": "Pending",
    },
    {
        "policy_number": "C24680",
        "billing_cycle": "Annual",
        "amount_due": 1000.0,
        "due_date": "2025-12-01",
        "status": "Pending",
    },
]


def get_billing_info(policy_number: str):
    """
    Retrieve billing information for a given policy_number.
    Return a JSON object with billing fields if found, or {"error": "Policy not found."} if missing.
    """
    print(f"[Tool] Retrieving billing info for policy number: {policy_number}")
    for record in billing_database:
        if record["policy_number"] == policy_number.strip():
            return json.dumps(record)
    return json.dumps({"error": "Policy not found."})


def update_billing_info(policy_number: str, field: str, new_value: str):
    """
    Update a given field in the billing record for the specified policy_number.
    Return the updated record as JSON if successful, or an error message if policy not found.
    """
    print(
        f"[Tool] Updating billing info for policy {policy_number}: {field} -> {new_value}"
    )
    for record in billing_database:
        if record["policy_number"] == policy_number.strip():
            if field in record:
                if field == "amount_due":
                    try:
                        record[field] = float(new_value)
                    except ValueError:
                        return json.dumps(
                            {"error": f"Invalid numeric value for {field}: {new_value}"}
                        )
                else:
                    record[field] = new_value
                return json.dumps(record)
            else:
                return json.dumps(
                    {"error": f"Field '{field}' not found in billing record."}
                )
    return json.dumps({"error": "Policy not found."})


billing_react = dspy.ReAct(
    BillingAgentSignature, tools=[get_billing_info, update_billing_info]
)


@billing_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "billing_request"
)
async def handle_billing_message(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"
        response = billing_react(chat_history=conversation_string)
        final_text = response.final_response
        meta = msg.get("meta", {})
        meta["agent"] = "BillingAgent"
        await human_channel.publish(
            {
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": final_text,
            }
        )
    except Exception as e:
        print(f"Error in BillingAgent: {e}")


if __name__ == "__main__":
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=language_model)
    test_conversation = (
        "User: Hi, I'd like to know my next billing date.\n"
        "BillingAgent: Sure! Please provide your policy number.\n"
        "User: It's B67890.\n"
    )
    result = billing_react(chat_history=test_conversation)
    print("BillingAgent says:")
    print(result.final_response)
