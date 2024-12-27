import asyncio
import sys

from rich.console import Console
from rich.prompt import Prompt

from eggai import Agent
from memory import messages_history_memory
from shared import agents_channel, humans_channel

console = Console()

chat_display_agent = Agent(name="ChatDisplayAgent")

AGENT_STYLES = {
    "TriageAgent": {"emoji": "🛠️", "color": "cyan"},
    "ClaimsAgent": {"emoji": "📝", "color": "red"},
    "PolicyAgent": {"emoji": "📄", "color": "green"},
    "EscalationAgent": {"emoji": "⚠️", "color": "yellow"},
    "Assistant": {"emoji": "💬", "color": "cyan"},
}


def clear_last_line():
    sys.stdout.write("\x1b[2K")  # Clear the entire line

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
