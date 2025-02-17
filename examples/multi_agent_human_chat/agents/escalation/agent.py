import json
from uuid import uuid4
import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent
import asyncio
from typing import Literal

# Agent & Channels
escalation_agent = Agent(name="EscalationAgent")
agents_channel = Channel("agents")
human_channel = Channel("human")
pending_tickets = {}
ticket_database = [{
    "ticket_id": "ESC-123456",
    "department": "Technical Support",
    "issue": "Billing issue",
    "notes": "User reported an error on the website.",
    "customer_name": "John Doe",
    "policy_number": "P123456",
    "contact_info": "john@example.com"
}]

# Tools
def create_ticket(dept, issue, notes, cust_name, policy, contact):
    ticket_id = f"ESC-{len(ticket_database) + 1:06d}"
    ticket = {
        "ticket_id": ticket_id,
        "department": dept,
        "issue": issue,
        "notes": notes,
        "customer_name": cust_name,
        "policy_number": policy,
        "contact_info": contact
    }
    ticket_database.append(ticket)
    return json.dumps(ticket)

def retrieve_ticket(ticket_id):
    for t in ticket_database:
        if t["ticket_id"] == ticket_id:
            return json.dumps(t)
    return json.dumps({"error": "Ticket not found."})

# Classifier Module
class EscalationAgentClassifierSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    missing_required_fields: list = dspy.OutputField(desc="List of missing required fields.")
    next_step: Literal["ask_additional_data", "ask_confirmation", "create_ticket"] = dspy.OutputField(desc="Current escalation step.")

escalation_classifier = dspy.ChainOfThought(EscalationAgentClassifierSignature)

# Ask Additional Data Module
class AskAdditionalDataSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    missing_fields: list = dspy.InputField(desc="Missing fields to ask.")
    final_message: str = dspy.OutputField(desc="Message asking for additional data.")

ask_additional_data_module = dspy.ChainOfThought(AskAdditionalDataSignature)

# Ask Confirmation Module
class AskConfirmationSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    final_message: str = dspy.OutputField(desc="Message asking for confirmation.")

ask_confirmation_module = dspy.ChainOfThought(AskConfirmationSignature)

# Create Ticket Module
class CreateTicketSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation result.")

create_ticket_module = dspy.ReAct(CreateTicketSignature, tools=[create_ticket, retrieve_ticket])

def chat_history_to_text(chat_history: list) -> str:
    return " ".join(msg.get("content", "") for msg in chat_history)

def update_session_data(session: str, data: dict):
    if session not in pending_tickets:
        pending_tickets[session] = {}
    pending_tickets[session].update(data)

def internal_router(session: str, chat_history: list) -> str:
    text = chat_history_to_text(chat_history)
    classifier_result = escalation_classifier(chat_history=text)
    missing_fields = classifier_result.missing_required_fields
    step = classifier_result.next_step
    if step == "ask_additional_data":
        response = ask_additional_data_module(session_details=pending_tickets[session], missing_fields=missing_fields).final_message
    elif step == "ask_confirmation":
        response = ask_confirmation_module(session_details=pending_tickets[session]).final_message
    elif step == "create_ticket":
        response = create_ticket_module(session_details=pending_tickets[session]).ticket_message
        pending_tickets.pop(session, None)
    else:
        response = "Unexpected state."
    return response

@escalation_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_update"
)
async def handle_escalation_update(msg):
    meta = msg.get("meta", {})
    session = meta.get("session", str(uuid4()))
    meta["session"] = session
    payload = msg.get("payload", {})
    chat_history = payload.get("chat_history", [])
    if "data" in payload:
        update_session_data(session, payload["data"])
    if session not in pending_tickets:
        pending_tickets[session] = {}
    response = internal_router(session, chat_history)
    # Append agent response to chat history
    chat_history.append({"role": "EscalationAgent", "content": response})
    await human_channel.publish({
        "id": str(uuid4()),
        "type": "agent_message",
        "meta": meta,
        "payload": {"chat_history": chat_history, "message": response}
    })

if __name__ == "__main__":
    async def test_conversation():
        load_dotenv()
        language_model = dspy.LM("openai/gpt-4o-mini")
        dspy.configure(lm=language_model)
        await escalation_agent.start()
        await human_channel.start()
        human_channel.subscribe(lambda msg: print("[Human]", msg))
        agents_channel.subscribe(lambda msg: print("[Agents]", msg))
        session = "session_test_001"
        history = []

        history.append({"role": "User", "content": "I need help with my billing. I'm getting an error."})
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.sleep(1)

        history.append({"role": "User", "content": "My name is Alice, policy number is P789012, contact info is alice@example.com."})
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {
                "chat_history": history,
                "data": {
                    "customer_name": "Alice Smith",
                    "policy_number": "P789012",
                    "contact_info": "alice@example.com"
                }
            }
        })
        await asyncio.sleep(1)

        history.append({"role": "User", "content": "Yes, please create the ticket."})
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.sleep(1)
        await asyncio.Future()

    asyncio.run(test_conversation())
