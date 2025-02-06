import json
from uuid import uuid4
import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent

escalation_agent = Agent(name="EscalationAgent")

agents_channel = Channel("agents")
human_channel = Channel("human")


class EscalationAgentSignature(dspy.Signature):
    """
    You are the Escalation Assistant within an insurance customer service system.

    ROLE:
      - Handle issues that the ClaimsAgent or PoliciesAgent cannot resolve.
      - Inform the user politely that their issue will be escalated to a human representative.
      - Generate a unique ticket ID for reference (e.g., ESC-123456).
      - Specify the appropriate department or team (e.g., "Technical Support", "Billing")
        that will address the issue.

    GUIDELINES:
      - Maintain a polite and professional tone.
      - Avoid speculative or incorrect information.
      - Ensure the ticket ID follows the format 'ESC-XXXXXX' (6 digits).
      - You Always ask confirm before creating a ticket, showing the user what are you filling details
        and ask for confirmation. Never create a ticket without asking more details.
      - You don't know the ticket ID before creating it, so you need to generate it.

    Input Fields:
      - chat_history: A string containing the conversation context so far.

    Output Fields:
      - final_response: The final text response to the user.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    final_response: str = dspy.OutputField(
        desc="Escalation message including ticket ID and department."
    )


ticket_database = [
    {
        "ticket_id": "ESC-123456",
        "department": "Technical Support",
        "issue": "Billing issue",
        "notes": "User reported an error on the website.",
    }
]


def create_ticket(department, issue_description, notes):
    """
    Create a ticket and return it as a JSON object with:
      - ticket_id (e.g., ESC-123456)
      - department (e.g., Technical Support)
      - issue (brief description of the user's problem)
    """
    print("[Tool] Creating ticket for:", department, "-", issue_description)
    ticket_id = f"ESC-{len(ticket_database) + 1:06d}"  # e.g. ESC-000002
    ticket_database.append(
        {
            "ticket_id": ticket_id,
            "department": department,
            "issue": issue_description,
            "notes": notes,
        }
    )
    return json.dumps(ticket_database[-1])


def retrieve_ticket(ticket_id):
    """
    Return ticket details (as JSON) for ticket_id,
    or an error message if the ticket isn't found.
    """
    print("[Tool] Retrieving ticket details for:", ticket_id)
    for ticket in ticket_database:
        if ticket["ticket_id"] == ticket_id:
            return json.dumps(ticket)
    return json.dumps({"error": "Ticket not found."})


escalation_react = dspy.ReAct(
    EscalationAgentSignature, tools=[create_ticket, retrieve_ticket]
)


@escalation_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_request"
)
async def handle_escalation(msg):
    try:
        # Convert chat messages into a single conversation string
        chat_messages = msg["payload"]["chat_messages"]
        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"

        # Generate the ReAct result
        response = escalation_react(chat_history=conversation_string)
        final_text = response.final_response

        # Publish the response back to the user
        meta = msg.get("meta", {})
        meta["agent"] = "EscalationAgent"
        await human_channel.publish(
            {
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": final_text,
            }
        )
    except Exception as e:
        print(f"Error in EscalationAgent: {e}")


if __name__ == "__main__":
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=language_model)
    # Quick test of the chain directly
    test_conversation = (
        "User: My issue wasn't resolved by PoliciesAgent. I'm still having trouble.\n"
        "EscalationAgent: Certainly. Could you describe the issue in more detail?\n"
        "User: It's about my billing setup. The website keeps throwing an error.\n"
    )
    result = escalation_react(chat_history=test_conversation)
    print("EscalationAgent says:")
    print(result.final_response)
