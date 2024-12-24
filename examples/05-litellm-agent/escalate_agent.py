import json
import random

from eggai import Channel
from lite_llm_agent import LiteLlmAgent
from tests.test_events import channel

agents_channel = Channel("agents")
humans_channel = Channel("humans")

# Initialize EscalationAgent
escalation_agent = LiteLlmAgent(
    name="EscalationAgent",
    system_message=(
        "You handle complex customer issues and create support tickets. You receive an issue statement from the user and "
        "create a support ticket. You always respond with the ticket info generated as JSON { \"ticket_id\": \"...\", \"department\": \"...\" }"
    ),
    model="openai/gpt-3.5-turbo"
)

@escalation_agent.tool()
def create_ticket(issue, department, additional_details):
    """
    Creates a new support tickets and return the ticket as JSON object string.

    :param issue: The issue for which the ticket is being created.
    :param department: The department to which the ticket will be assigned, can be "Billing Department", "Technical Department", or "General" as fallback.
    :param additional_details: Additional details about the issue if needed.
    """
    print(f"Creating support ticket for issue: {issue}")
    # Simulate ticket creation
    ticket_id = "TCKT" + str(random.randint(1000, 9999))
    return {"ticket_id": ticket_id, "subject": issue, "additional_details": additional_details, "status": "Open", "department": department}

# Subscribe EscalationAgent to handle escalated requests
@escalation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalate_request")
async def handle_escalation(msg):
    response = await escalation_agent.completion(messages=[{
        "role": "user",
        "content": "Please create a ticket for the following issue: " + msg["payload"] + " and return it as plain JSON string, no markdown."
    }])
    ticket = json.loads(response.choices[0].message.content.strip())
    print("Ticket created for escalated issue: ", ticket)
    await agents_channel.publish({
        "type": "new_ticket",
        "payload": ticket
    })

    # Inform customer about escalation
    await humans_channel.publish({
        "type": "escalated",
        "payload": f"Your issue has been escalated. Ticket ID: {ticket['ticket_id']}, department: {ticket['department']}"
    })
