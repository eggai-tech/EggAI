import json
from uuid import uuid4
import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent
import asyncio
from typing import Any, Literal, Optional

# Agent & Channels
escalation_agent = Agent(name="EscalationAgent")
agents_channel = Channel("agents")
human_channel = Channel("human")
pending_tickets = {}

ticket_database = [{
    "id": "TICKET-001",
    "department": "Technical Support",
    "title": "Billing issue",
    "contact_info": "john@example.com"
}]

def create_ticket(dept, title, contact):
    """
    Create a ticket with only the department, title, and contact_info fields.
    """
    print("[TOOL] Creating ticket...")
    ticket = {
        "id": f"TICKET-{len(ticket_database) + 1:03}",
        "department": dept,
        "title": title,
        "contact_info": contact
    }
    ticket_database.append(ticket)
    return json.dumps(ticket)

class RetrieveTicketInfoSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    department: Literal["Technical Support", "Billing", "Sales"] = dspy.OutputField(desc="Department of destination of ticket.")
    title: str = dspy.OutputField(desc="Title of the ticket.")
    contact_info: str = dspy.OutputField(desc="Contact information of the user.")
    info_complete: bool = dspy.OutputField(desc="Whether all required information is present in the chat history or not.")
    message: Optional[str] = dspy.OutputField(desc="Message to the user, asking for missing information or confirmation.")
    

retrieve_ticket_info_module = dspy.asyncify(dspy.ChainOfThought(RetrieveTicketInfoSignature))

class ClassifyConfirmationSignature(dspy.Signature):
    chat_history: str = dspy.InputField(desc="Full conversation context.")
    confirmation: Literal["yes", "no"] = dspy.OutputField(desc="User confirmation retrieved from chat history.")
    message: Optional[str] = dspy.OutputField(desc="Message to the user, asking for confirmation.")

classify_confirmation = dspy.asyncify(dspy.ChainOfThought(ClassifyConfirmationSignature))

class CreateTicketSignature(dspy.Signature):
    ticket_details: dict = dspy.InputField(desc="Session details.")
    ticket_message: str = dspy.OutputField(desc="Ticket creation message confirmation, with summary of ticket details.")

# Now only using the create_ticket tool (retrieve_ticket removed)
create_ticket_module = dspy.asyncify(dspy.ReAct(CreateTicketSignature, tools=[create_ticket]))

def chat_history_to_text(chat_history: list) -> str:
    return " ".join(msg.get("content", "") for msg in chat_history)

def update_session_data(session: str, data: dict):
    if session not in pending_tickets:
        pending_tickets[session] = {}
    pending_tickets[session].update(data)

async def agentic_workflow(session: str, chat_history: list, meta: Any) -> str:
    text = chat_history_to_text(chat_history)
    step = pending_tickets[session].get("step", "ask_additional_data")

    if step == "ask_additional_data":
        response = await retrieve_ticket_info_module(chat_history=text)
        if response.title:
            update_session_data(session, {"title": response.title})
        if response.contact_info:
            update_session_data(session, {"contact_info": response.contact_info})
        if response.department:
            update_session_data(session, {"department": response.department})
        if response.info_complete:
            update_session_data(session, {"step": "ask_confirmation"})
            conf_message = (await classify_confirmation(chat_history=text)).message
            chat_history.append({"role": "EscalationAgent", "content": conf_message})
            await human_channel.publish({
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": {"chat_history": chat_history, "message": conf_message}
            })
        else:
            chat_history.append({"role": "EscalationAgent", "content": response.message})
            await human_channel.publish({
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": {"chat_history": chat_history, "message": response.message}
            })
    elif step == "ask_confirmation":
        response = (await classify_confirmation(chat_history=text))
        if response.confirmation == "yes":
            update_session_data(session, {"step": "create_ticket"})
            chat_history.append({"role": "EscalationAgent", "content": "Creating ticket..."})
            await human_channel.publish({
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": {"chat_history": chat_history, "message": "Creating ticket..."}
            })
            await agentic_workflow(session, chat_history, meta)
        else:
            chat_history.append({"role": "EscalationAgent", "content": response.message})
            await human_channel.publish({
                "id": str(uuid4()),
                "type": "agent_message",
                "meta": meta,
                "payload": {"chat_history": chat_history, "message": response.message}
            })
    elif step == "create_ticket":
        response = (await create_ticket_module(ticket_details=pending_tickets[session])).ticket_message
        chat_history.append({"role": "EscalationAgent", "content": response})
        await human_channel.publish({
            "id": str(uuid4()),
            "type": "agent_message",
            "meta": meta,
            "payload": {"chat_history": chat_history, "message": response}
        })
        pending_tickets.pop(session, None)
    else:
        raise ValueError("Invalid step value.")

# --- Entrypoint Subscription ---
@escalation_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_request"
)
async def handle_escalation_request(msg):
    meta = msg.get("meta", {})
    session = meta.get("session", str(uuid4()))
    meta["session"] = session
    payload = msg.get("payload", {})
    chat_history = payload.get("chat_history", [])
    if session not in pending_tickets:
        pending_tickets[session] = { "step": "ask_additional_data" }
    await agentic_workflow(session, chat_history, meta)

# --- Test Conversation ---
if __name__ == "__main__":
    async def test_conversation():
        logger_agent = Agent(name="LoggerAgent")
        @logger_agent.subscribe(channel=human_channel)
        async def log_human_messages(msg):
            print("Agent Says:", msg["payload"]["message"])
        load_dotenv()
        language_model = dspy.LM("openai/gpt-4o-mini", cache=False)
        dspy.configure(lm=language_model)
        await logger_agent.start()
        await escalation_agent.start()
        session = "session_test_001"
        history = []

        history.append({"role": "User", "content": "I have a billing issue."})
        print("User Says: I have a billing issue.")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_request",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.sleep(5)

        # Step 2: User provides account details (contact_info)
        history.append({"role": "User", "content": "My contact info is alice@example.com"})
        print("User Says: My contact info is alice@example.com")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_request",
            "meta": {"session": session},
            "payload": {
                "chat_history": history,
            }
        })
        await asyncio.sleep(1)

        # Step 3: User confirms ticket creation
        history.append({"role": "User", "content": "Yes, please create the ticket."})
        print("User Says: Yes, please create the ticket.")
        await agents_channel.publish({
            "id": str(uuid4()),
            "type": "escalation_request",
            "meta": {"session": session},
            "payload": {"chat_history": history}
        })
        await asyncio.Future()

    asyncio.run(test_conversation())
