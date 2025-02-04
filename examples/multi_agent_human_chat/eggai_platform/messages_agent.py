import json
import os
from eggai import Channel, Agent

# Define channels
human_channel = Channel("human")
eggai_platform_channel = Channel("EggAI_Platform_Commands")

messages_agent = Agent(name="Eggai:MessagesAgent")
MESSAGES_FILE = "messages.json"


def load_messages(file_path: str):
    """Load messages from a JSON file. Returns a list of message dicts."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
    return []


def save_messages(file_path: str, messages):
    """Save the messages list to a JSON file."""
    try:
        with open(file_path, "w") as f:
            json.dump(messages, f, indent=2)
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")


def get_messages_for_chat(messages, chat_id):
    """Return messages belonging to a specific chat_id."""
    return [msg for msg in messages if msg.get("meta", {}).get("chat_id") == chat_id]


def get_chat_ids(messages):
    """Return a list of unique chat_ids found in the messages."""
    chat_ids = {msg.get("meta", {}).get("chat_id") for msg in messages if msg.get("meta", {}).get("chat_id")}
    return list(chat_ids)


@messages_agent.subscribe(
    channel=eggai_platform_channel,
    filter_func=lambda msg: "action" in msg
)
async def handle_command(msg):
    """
    Handle commands from the EggAI platform.

    Supported commands:
      - "list_messages": returns all stored messages.
      - "retrieve_messages": expects a chat_id in msg["meta"]["chat_id"] and returns messages for that chat.
      - "retrieve_chats_list": returns a list of unique chat IDs.
    """
    cmd = msg.get("action")
    msg_id = msg.get("id")
    messages = load_messages(MESSAGES_FILE)

    if cmd == "retrieve_messages":
        # Expect chat_id in msg["meta"]
        chat_id = msg.get("meta", {}).get("chat_id")
        if not chat_id:
            payload = {"error": "chat_id not provided for retrieve_messages"}
        else:
            payload = get_messages_for_chat(messages, chat_id)

    elif cmd == "retrieve_chats_list":
        payload = get_chat_ids(messages)

    else:
        payload = {"error": f"Unknown command: {cmd}"}

    await eggai_platform_channel.publish({
        "payload": payload,
        "meta": {"message_id": msg_id}
    })


@messages_agent.subscribe(
    channel=human_channel,
    filter_func=lambda msg: msg.get("type") in ["user_message", "agent_message"]
)
async def handle_human_message(msg):
    """
    Save incoming human (or agent) messages.

    Each message is expected to include a 'chat_id' in its 'meta' field.
    If absent, a default chat_id ("default") will be assigned.
    """
    try:
        # Ensure the message includes a chat_id in the meta information.
        if "meta" not in msg or "chat_id" not in msg.get("meta", {}):
            msg.setdefault("meta", {})["chat_id"] = "default"

        if "chat_messages" in msg["payload"]:
            msg["payload"] = msg["payload"]["chat_messages"][-1]

        messages = load_messages(MESSAGES_FILE)
        messages.append(msg)
        save_messages(MESSAGES_FILE, messages)
    except Exception as e:
        print("Error in MessageAgent:", e)
