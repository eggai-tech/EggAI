import asyncio
import json
import sys

from rich.console import Console
from rich.prompt import Prompt

from eggai import Channel, Agent
from lite_llm_agent import LiteLlmAgent

console = Console()

agents_channel = Channel("cli.agents")
humans_channel = Channel("cli.humans")

AGENT_REGISTRY = {
    "PolicyAgent": {
        "description": "Handles policy-related inquiries.",
        "keywords": ["policy details", "coverage", "premiums", "policy changes", "policy number", "renewal"]
    },
    "ClaimsAgent": {
        "description": "Handles claims-related inquiries.",
        "keywords": ["file a claim", "claim status", "claim amount", "accident", "damage", "incident"]
    },
    "EscalationAgent": {
        "description": "Handles escalated inquiries and out-of-scope requests.",
        "keywords": ["escalate", "speak to a human", "complaint", "refund", "support", "issue", "problem"]
    },
}

def build_triage_system_prompt(agent_registry):
    guidelines = "Guidelines:\n"
    for agent_name, agent_info in agent_registry.items():
        if agent_name != "EscalationAgent":
            keywords = ", ".join(agent_info.get("keywords", []))
            guidelines += (
                f"• If the user is asking about {keywords}, target = '{agent_name}'.\n"
            )
    guidelines += (
        "• If you cannot determine the category or if the request is out of scope, target = 'EscalationAgent'.\n"
        "• If the request is unclear but appears to require human support, forward to EscalationAgent.\n"
    )
    guidelines += (
        "Respond only with a JSON object indicating the target agent. Do not include any additional text or explanation.\n"
        "Example: {\"target\": \"ClaimsAgent\"}\n"
        "Remember: You must never provide any text other than the JSON object with the key 'target'."
    )

    system_prompt = f"""
You are an advanced Triage Assistant for a multi-agent system. Your primary responsibility is to analyze the user’s message and determine the most appropriate agent to handle the request.

{guidelines}
"""
    return system_prompt


triage_agent = LiteLlmAgent(
    name="TriageAgent",
    system_message=build_triage_system_prompt(AGENT_REGISTRY),
    model="gpt-3.5-turbo-1106"
)

claims_agent = LiteLlmAgent(
    name="ClaimsAgent",
    system_message=(
        "You are a Claims Assistant for an insurance company, specialized in handling inquiries related to claims. "
        "Examples of claims-related topics include:\n"
        "1. Filing a new claim\n"
        "2. Checking the status of an existing claim\n"
        "3. Understanding claim coverage or payouts\n"
        "\n"
        "When responding to users:\n"
        "• Provide clear instructions on how to file a claim if needed.\n"
        "• If a claim ID is provided, use it to check or update the status.\n"
        "• Be concise but thorough in your responses.\n"
        "• Always maintain a polite and empathetic tone.\n"
        "\n"
        "If the request extends beyond your scope or requires further escalation, ask the TriageAgent to forward the conversation to the EscalationAgent."
    ),
    model="gpt-3.5-turbo-1106"
)

policy_agent = LiteLlmAgent(
    name="PolicyAgent",
    system_message=(
        "You are the Policy Agent for an insurance company. "
        "Your job is to answer questions about policies: coverage details, premiums, and policy changes. "
        "\n\n"
        "Key Instructions:\n"
        "1. Always identify yourself as the 'Policy Agent.' Never call yourself the 'Claims Agent' or 'Escalation Agent.'\n"
        "2. If a user needs policy details, request their policy number (if not already provided). "
        "   If the user does not have a policy number, ask for their full name.\n"
        "3. Use the tool 'get_policy_details' to fetch policy information, which includes:\n"
        "   - Policyholder's name\n"
        "   - Policy type\n"
        "   - Coverage details\n"
        "   - Premium amount\n"
        "   - Premium due date\n"
        "4. If you cannot find the policy by either policy number or policyholder name, respond with 'Policy not found.' "
        "   and ask for clarification.\n"
        "5. If the question goes beyond policy details (e.g., filing a claim), forward it to the TriageAgent.\n"
        "\n"
        "Remember: You are the Policy Agent, and you handle policy-related inquiries. Stay within your scope, "
        "and always be polite, concise, and helpful."
    ),
    model="gpt-3.5-turbo-1106"
)

policies_database = [
    {"policy_number": "A12345", "name": "John Doe", "coverage_details": "Comprehensive", "premium_amount": 500, "due_date": "2025-01-01"},
    {"policy_number": "B67890", "name": "Jane Smith", "coverage_details": "Liability", "premium_amount": 300, "due_date": "2025-02-01"},
    {"policy_number": "C24680", "name": "Alice Johnson", "coverage_details": "Collision", "premium_amount": 400, "due_date": "2025-03-01"},
]

@policy_agent.tool()
async def get_policy_details(policy_number: str):
    """
    Get policy details for a given policy number.

    :param policy_number: The policy number to fetch details for.

    :return: The policy details as a JSON object.
    """
    print(f"[TOOL CALL] get_policy_details: {policy_number}")
    for policy in policies_database:
        if policy["policy_number"] == policy_number:
            return json.dumps(policy)

    return "Policy not found."

escalation_agent = LiteLlmAgent(
    name="EscalationAgent",
    system_message=(
        "You are an Escalation Assistant for an insurance customer service system. "
        "You handle cases that cannot be resolved by the ClaimsAgent or PolicyAgent. "
        "\n\n"
        "Your tasks:\n"
        "• Provide a response politely informing the user that their issue will be escalated to a human support representative.\n"
        "• Generate a ticket ID for reference (e.g., ESC-123456).\n"
        "• Indicate the department or team (e.g., 'Technical Support', 'Billing', etc.) that will handle the issue.\n"
        "\n"
        "Example response:\n"
        "    'We have created a support ticket ESC-123456 for your issue. Our Technical Support team will reach out to you shortly.'\n"
        "Maintain a courteous tone and avoid providing any incorrect or speculative information. "
    ),
    model="gpt-3.5-turbo-1106"
)

# Define emojis and colors for agents
AGENT_STYLES = {
    "TriageAgent": {"emoji": "🛠️", "color": "cyan"},
    "ClaimsAgent": {"emoji": "📝", "color": "red"},
    "PolicyAgent": {"emoji": "📄", "color": "green"},
    "EscalationAgent": {"emoji": "⚠️", "color": "yellow"},
    "Assistant": {"emoji": "💬", "color": "cyan"},
}


@triage_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "user_message")
async def handle_user_message(msg):
    try:
        payload = msg["payload"]
        chat_messages = payload.get("chat_messages", [])

        # identify the agent to target based on the user chat messages
        response = await triage_agent.completion(messages=[{
            "role": "user",
            "content": json.dumps(chat_messages),
        }])

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            await agents_channel.publish({
                "type": "response",
                "agent": "TriageAgent",
                "payload": "There was an error processing your request. Please try again."
            })
            return

        target_agent = reply.get("target")


        conversation_string = ""
        for chat in chat_messages:
            user = chat.get("agent", "User")
            conversation_string += f"{user}: {chat['content']}\n"

        triage_to_agent_messages = [{
            "role": "user",
            "content": f"You are {target_agent}, please continue the conversation. \n\n{conversation_string}",
        }]

        if target_agent == "ClaimsAgent":
            await agents_channel.publish({
                "type": "claims_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        elif target_agent == "PolicyAgent":
            await agents_channel.publish({
                "type": "policy_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        elif target_agent == "EscalationAgent":
            await agents_channel.publish({
                "type": "escalation_request",
                "payload": {
                    "chat_messages": triage_to_agent_messages
                },
            })
        else:
            await agents_channel.publish({
                "type": "response",
                "agent": "TriageAgent",
                "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?",
            })
    except Exception as e:
        print("Error in TriageAgent: ", e)
        console.print(f"[red]Error in TriageAgent: {e}[/red]")


# ClaimsAgent subscribes to claims requests
@claims_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "claims_request")
async def handle_claims_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await claims_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "ClaimsAgent"})

        await agents_channel.publish({
            "type": "response",
            "agent": "ClaimsAgent",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        console.print(f"[red]Error in ClaimsAgent: {e}[/red]")

# PolicyAgent subscribes to policy requests
@policy_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "policy_request")
async def handle_policy_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await policy_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "PolicyAgent"})

        await agents_channel.publish({
            "type": "response",
            "agent": "PolicyAgent",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        console.print(f"[red]Error in PolicyAgent: {e}[/red]")


# EscalationAgent subscribes to escalation requests
@escalation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_request")
async def handle_escalation_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await claims_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "EscalationAgent"})

        await agents_channel.publish({
            "type": "response",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        console.print(f"[red]Error in EscalationAgent: {e}[/red]")



# Initialize ChatDisplayAgent
chat_display_agent = Agent(name="ChatDisplayAgent")


def clear_last_line():
    sys.stdout.write("\x1b[2K")  # Clear the entire line


# ChatDisplayAgent subscribes to responses and prints them
@chat_display_agent.subscribe(channel=agents_channel,
                              filter_func=lambda msg: msg["type"] == "response")
async def display_response(msg):
    try:
        agent_name = msg.get("agent", "Assistant")
        chat_messages = msg.get("payload", {}).get("chat_messages", [])
        response = chat_messages[-1]["content"]
        style = AGENT_STYLES.get(agent_name, {"emoji": "❓", "color": "magenta"})
        emoji = style["emoji"]
        color = style["color"]
        clear_last_line()
        console.print(f"\n{emoji} [bold {color}]{agent_name}[/bold {color}]:\n\t{response}")
        console.print("\n[bold cyan]You[/bold cyan]: ", end="")
    except Exception as e:
        console.print(f"[red]Error in ChatDisplayAgent: {e}[/red]")

messages_history_memory = []

@triage_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "response")
async def triage_write_memory(msg):
    try:
        chat_messages = msg.get("payload", {}).get("chat_messages", [])
        messages_history_memory.clear()
        messages_history_memory.extend(chat_messages)
    except Exception as e:
        console.print(f"[red]Error in TriageAgent: {e}[/red]")

async def ask_input(stop_event):
    loop = asyncio.get_event_loop()
    while not stop_event.is_set():
        try:
            # Run the blocking Prompt.ask in a separate thread
            user_input = await loop.run_in_executor(
                None, lambda: Prompt.ask("\n[bold cyan]You[/bold cyan]", show_default=False)
            )
            if user_input.lower() in {"exit", "quit"}:
                console.print("\n[bold red]Goodbye![/bold red]")
                stop_event.set()
                break
            elif user_input.strip() == "":
                continue  # Ignore empty inputs
            else:
                messages_history_memory.append({"role": "user", "content": user_input})
                await humans_channel.publish({
                    "type": "user_message",
                    "payload": {
                        "chat_messages": messages_history_memory,
                    },
                })
        except Exception as e:
            stop_event.set()


# Function to start all agents
async def start_agents():
    await asyncio.gather(
        triage_agent.run(),
        claims_agent.run(),
        policy_agent.run(),
        escalation_agent.run(),
        chat_display_agent.run()
    )


# Function to stop all agents
async def stop_agents():
    await asyncio.gather(
        triage_agent.stop(),
        claims_agent.stop(),
        policy_agent.stop(),
        escalation_agent.stop(),
        chat_display_agent.stop()
    )
    await Channel.stop()


async def main():
    stop_event = asyncio.Event()
    try:
        console.print("[bold cyan]Welcome to the Insurance Customer Service System![/bold cyan]")
        await start_agents()
        asyncio.create_task(ask_input(stop_event))
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await stop_agents()


# Entry point
if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting...[/bold red]")
