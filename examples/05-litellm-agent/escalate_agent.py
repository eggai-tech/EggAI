from eggai import Channel
from lite_llm_agent import LiteLlmAgent

agents_channel = Channel("agents")
humans_channel = Channel("humans")

# Initialize EscalationAgent
escalation_agent = LiteLlmAgent(
    name="EscalationAgent",
    system_message="You handle complex customer issues and create support tickets.",
    model="openai/gpt-4"
)


# Define EscalationAgent's Tool
@escalation_agent.tool(name="TicketingTool", description="Creates and manages support tickets.")
def ticketing_tool(issue):
    """
    Creates and manages support tickets.

    :param issue: The issue for which the ticket is being created.
    """
    print(f"Creating support ticket for issue: {issue}")
    # Simulate ticket creation
    ticket_id = "TCKT123456"
    return {"ticket_id": ticket_id, "issue": issue, "status": "Open"}


# Subscribe EscalationAgent to handle escalated requests
@escalation_agent.subscribe(filter_func=lambda msg: msg["type"] == "escalate_request")
async def handle_escalation(msg):
    # Create a support ticket
    ticket = ticketing_tool(msg["payload"])

    print("Escalating issue to support team...")
    # Notify support team
    await agents_channel.publish({
        "type": "new_ticket",
        "payload": ticket
    })

    print(f"Support ticket created: {ticket['ticket_id']}, informing customer...")
    # Inform customer about escalation
    await humans_channel.publish({
        "type": "escalated",
        "payload": f"Your issue has been escalated. Ticket ID: {ticket['ticket_id']}"
    })
