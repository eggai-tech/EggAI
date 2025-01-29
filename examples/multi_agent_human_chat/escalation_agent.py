from uuid import uuid4

from eggai import Channel
from lite_llm_agent import LiteLlmAgent

agents_channel = Channel("agents")
human_channel = Channel("human")

escalation_agent = LiteLlmAgent(
    name="EscalationAgent",
    system_message=(
        "You are the Escalation Assistant within an insurance customer service system. "
        "Your role is to handle inquiries and issues that cannot be resolved by the ClaimsAgent or PoliciesAgent.\n\n"
        "Your Responsibilities:\n"
        "• Politely inform the user that their issue will be escalated to a human support representative.\n"
        "• Generate a unique ticket ID for reference (e.g., ESC-123456).\n"
        "• Specify the appropriate department or team (e.g., 'Technical Support', 'Billing') that will address the issue.\n\n"
        "Response Format:\n"
        "Provide a concise, courteous message following this structure:\n"
        "    'We have created a support ticket ESC-123456 for your issue. Our Technical Support team will reach out to you shortly.'\n\n"
        "Guidelines:\n"
        "• Maintain a polite and professional tone.\n"
        "• Do not provide speculative or incorrect information.\n"
        "• Ensure the ticket ID follows the format 'ESC-XXXXXX' where 'X' is a digit.\n"
    ),
    model="openai/gpt-4o-mini",
)

ticket_database = [{
    "ticket_id": "ESC-123456",
    "department": "Technical Support",
    "issue": "Billing issue",
}]

@escalation_agent.tool()
def create_ticket(department, issue):
    """
    Create a ticket and return as JSON object with fields:
    - ticket_id: str (e.g., "ESC-123456")
    - department: str (can be "Technical Support" or "Billing")
    - issue: str (e.g., "Billing issue")

    :arg department: str - The department or team that will handle the issue, can be "Technical Support" or "Billing".
    :arg issue: str - The issue or problem that the user is facing.
    """
    print("[Tool] Creating ticket for:", department, "-", issue)
    ticket_id = f"ESC-{len(ticket_database) + 1}"
    ticket_database.append({
        "ticket_id": ticket_id,
        "department": department,
        "issue": issue,
    })
    return ticket_database[-1]

@escalation_agent.tool()
def retrieve_ticket(ticket_id):
    """
    Get the ticket details from the ticket ID. If the ticket is not found, return an error message.

    :arg ticket_id: str - The ticket ID to get the details for.
    """
    print("[Tool] Retrieving ticket details for:", ticket_id)
    for ticket in ticket_database:
        if ticket["ticket_id"] == ticket_id:
            return ticket

    return {"error": "Ticket not found."}

@escalation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_request")
async def handle_ticket_message(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await escalation_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        meta = msg.get("meta", {})
        meta["agent"] = "EscalationAgent"
        await human_channel.publish({
            "id": str(uuid4()),
            "type": "agent_message",
            "meta": meta,
            "payload": reply,
        })
    except Exception as e:
        print(f"Error in EscalationAgent: {e}")