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

# --- Classifier Module ---
class EscalationAgentClassifierSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    missing_required_fields: list[Literal["customer_name", "policy_number", "contact_info", "error_message"]] = dspy.OutputField(desc="List of missing required fields.")
    next_step: Literal["ask_additional_data", "ask_confirmation", "create_ticket"] = dspy.OutputField(desc="Current escalation step.")

escalation_classifier = dspy.ChainOfThought(EscalationAgentClassifierSignature)

# --- Additional Data Module ---
class AskAdditionalDataSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    missing_fields: list = dspy.InputField(desc="Missing fields to ask.")
    final_message: str = dspy.OutputField(desc="Message asking for additional data.")

ask_additional_data_module = dspy.ChainOfThought(AskAdditionalDataSignature)

# --- Confirmation Module ---
class AskConfirmationSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    final_message: str = dspy.OutputField(desc="Message asking for confirmation.")

ask_confirmation_module = dspy.ChainOfThought(AskConfirmationSignature)

# --- Create Ticket Module ---
class CreateTicketSignature(dspy.Signature):
    session_details: dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation result.")

create_ticket_module = dspy.ReAct(CreateTicketSignature, tools=[create_ticket, retrieve_ticket])

# --- Helper Functions ---
def chat_history_to_text(chat_history: list) -> str:
    return " ".join(msg.get("content", "") for msg in chat_history)

def update_session_data(session: str, data: dict):
    if session not in pending_tickets:
        pending_tickets[session] = {}
    pending_tickets[session].update(data)

def internal_router(session: str, chat_history: list) -> str:
    text = chat_history_to_text(chat_history)
    # Call the classifier module via dspy:
    classifier_result = escalation_classifier(chat_history=text)
    missing_fields = classifier_result.missing_required_fields
    step = classifier_result.next_step
    if step == "ask_additional_data":
        response = ask_additional_data_module(session_details=pending_tickets[session],
                                              missing_fields=missing_fields).final_message
    elif step == "ask_confirmation":
        response = ask_confirmation_module(session_details=pending_tickets[session]).final_message
    elif step == "create_ticket":
        details = pending_tickets[session]
        details.setdefault("department", "Technical Support")
        details.setdefault("issue", "Billing issue")
        details["notes"] = details.get("error_message", "No error message provided")
        response = create_ticket_module(session_details=details).ticket_message
        pending_tickets.pop(session, None)
    else:
        response = "Unexpected state."
    return response

# --- Entrypoint Subscription ---
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
    # Append the agent's response to the chat history
    chat_history.append({"role": "EscalationAgent", "content": response})
    await human_channel.publish({
        "id": str(uuid4()),
        "type": "agent_message",
        "meta": meta,
        "payload": {"chat_history": chat_history, "message": response}
    })

# --- Test Conversation ---
if __name__ == "__main__":
    async def test_conversation():
        logger_agent = Agent(name="LoggerAgent")
        @logger_agent.subscribe(channel=human_channel)
        async def log_human_messages(msg):
            print("Agent Says:", msg["payload"]["message"])
        load_dotenv()
        language_model = dspy.LM("openai/gpt-4o-mini")
        dspy.configure(lm=language_model)
        await logger_agent.start()
        await escalation_agent.start()
        session = "session_test_001"
        history = []

        # Step 1: User sends initial message (all required fields missing)
        history.append({"role": "User", "content": "I need help with my billing. I'm getting an error."})
        print("User Says: I need help with my billing. I'm getting an error.")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.sleep(1)

        # Step 2: User provides account details (still missing error_message)
        history.append({"role": "User", "content": "My name is Alice, policy number is P789012, contact info is alice@example.com."})
        print("User Says: My name is Alice, policy number is P789012, contact info is alice@example.com")
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

        # Step 3: User provides the error message (now all required fields are present)
        history.append({"role": "User", "content": "The error is connection timeout."})
        print("User Says: The error is connection timeout.")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {
                "chat_history": history,
                "data": {"error_message": "connection timeout"}
            }
        })
        await asyncio.sleep(1)

        # Step 4: User confirms ticket creation
        history.append({"role": "User", "content": "Yes, please create the ticket."})
        print("User Says: Yes, please create the ticket.")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_update",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.sleep(1)
        await asyncio.Future()

    asyncio.run(test_conversation())
