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
      - Handle issues that other agents could not solve.
      - Extract all relevant details dynamically from the conversation.
      - Inform the user politely that their issue will be escalated to a human representative.
      - Always acknowledge the user's **full issue**, including multiple concerns.
      - Always ask for confirmation before creating a ticket.
      - If the user confirms, generate a unique ticket ID (e.g., ESC-123456) and provide it.

    GUIDELINES:
      - Maintain a polite and professional tone.
      - Avoid speculative or incorrect information.
      - Ensure the ticket ID follows the format 'ESC-XXXXXX' (6 digits).
      - **Acknowledge ALL user-reported issues before asking for confirmation.**
      - Never generate a ticket before explicit confirmation from the user.
      - Identify the appropriate department for handling the issue.

    Input Fields:
      - chat_history: A string containing the conversation context.

    Output Fields:
      - acknowledgment: Acknowledgment of the user's issue.
      - confirmation_prompt: Message asking the user to confirm before ticket creation.
      - final_response: The final escalation message (either waiting for confirmation or providing ticket details).
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    acknowledgment: str = dspy.OutputField(
        desc="Acknowledgment of user-reported issue."
    )
    confirmation_prompt: str = dspy.OutputField(desc="Request for user confirmation.")
    final_response: str = dspy.OutputField(
        desc="Final escalation message, either confirmation or ticket details."
    )


ticket_database = []


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
    """
    Handles escalation requests:
    - Extracts issue details.
    - Acknowledges the issue.
    - Requests confirmation before proceeding with ticket creation.
    - If user confirms in the same message, creates the ticket.
    """
    try:
        chat_messages = msg["payload"]["chat_messages"]
        conversation_string = "\n".join(
            [f"{m['role']}: {m['content']}" for m in chat_messages]
        )

        escalation_react_async = dspy.asyncify(escalation_react)
        response = await escalation_react_async(chat_history=conversation_string)

        acknowledgment = response.acknowledgment
        confirmation_prompt = response.confirmation_prompt
        user_message = chat_messages[-1]["content"].strip().lower()

        if user_message in ["yes", "confirmed", "okay", "proceed", "go ahead"]:
            inferred_department = "Billing"  # Hardcoded for now
            extracted_issue = acknowledgment  # Use extracted issue from acknowledgment

            ticket_response = create_ticket(
                inferred_department, extracted_issue, "User confirmed escalation."
            )
            response_message = f"Your escalation has been processed. Here are the ticket details:\n{ticket_response}"
        else:
            response_message = f"{acknowledgment}\n\n{confirmation_prompt}"

        meta = msg.get("meta", {})
        meta["agent"] = "EscalationAgent"

        # Send acknowledgment, request confirmation, or final ticket response
        await human_channel.publish(
            {
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": response_message,
            }
        )

    except Exception as e:
        print(f"Error in EscalationAgent (confirmation step): {e}")


if __name__ == "__main__":
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=language_model)

    # Quick test of the chain directly
    test_conversation = (
        "User: My issue wasn't resolved. I'm still having trouble.\n"
        "EscalationAgent: Certainly. Could you describe the issue in more detail?\n"
        "User: It's about my billing setup. The website keeps throwing an error.\n"
    )
    result = escalation_react(chat_history=test_conversation)
    print("EscalationAgent says:")
    print(result.acknowledgment + "\n\n" + result.confirmation_prompt)
