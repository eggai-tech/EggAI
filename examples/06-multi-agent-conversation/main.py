import asyncio
import json
import sys
import threading

from eggai import Channel, Agent
from lite_llm_agent import LiteLlmAgent
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.prompt import Prompt
from rich import box

# Initialize Rich Console
console = Console()

# Define channels for agents and humans
agents_channel = Channel("cli.agents")
humans_channel = Channel("cli.humans")

# Initialize TriageAgent
triage_agent = LiteLlmAgent(
    name="TriageAgent",
    system_message=(
        "You are a triage assistant. Determine whether the user's message is about weather, math, or general inquiries. "
        "If it's weather-related, forward to WeatherAgent. If it's a math question, forward to MathAgent. "
        "Respond with a JSON object indicating the target agent. Example: {\"target\": \"WeatherAgent\"}."
    ),
    model="openai/gpt-3.5-turbo"
)

# Initialize WeatherAgent
weather_agent = LiteLlmAgent(
    name="WeatherAgent",
    system_message=(
        "You are a weather assistant. Provide accurate weather information based on user queries. "
        "Respond with a JSON object containing the key 'response' with your answer."
    ),
    model="openai/gpt-3.5-turbo"
)

# Initialize MathAgent
math_agent = LiteLlmAgent(
    name="MathAgent",
    system_message=(
        "You are a math assistant. Solve mathematical problems provided by the user. "
        "Respond with a JSON object containing the key 'response' with your answer."
    ),
    model="openai/gpt-3.5-turbo"
)

# Define emojis and colors for agents
AGENT_STYLES = {
    "TriageAgent": {"emoji": "🛠️", "color": "cyan"},
    "WeatherAgent": {"emoji": "☀️", "color": "blue"},
    "MathAgent": {"emoji": "➕", "color": "green"},
    "UnknownAgent": {"emoji": "❓", "color": "yellow"},
}

# TriageAgent subscribes to human messages and routes them
@triage_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "user_message")
async def handle_user_message(msg):
    try:
        user_content = msg["payload"]
        # Get routing decision from TriageAgent
        response = await triage_agent.completion(messages=[{
            "role": "user",
            "content": f"User message: {user_content}. Determine the appropriate agent and respond with JSON."
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
        if target_agent == "WeatherAgent":
            await agents_channel.publish({
                "type": "weather_request",
                "payload": user_content
            })
        elif target_agent == "MathAgent":
            await agents_channel.publish({
                "type": "math_request",
                "payload": user_content
            })
        else:
            await agents_channel.publish({
                "type": "response",
                "agent": "TriageAgent",
                "payload": "I'm sorry, I couldn't understand your request. Could you please clarify?"
            })
    except Exception as e:
        console.print(f"[red]Error in TriageAgent: {e}[/red]")

# WeatherAgent subscribes to weather requests
@weather_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "weather_request")
async def handle_weather_request(msg):
    try:
        query = msg["payload"]
        response = await weather_agent.completion(messages=[{
            "role": "user",
            "content": f"Provide weather information for: {query}. Respond as JSON with key 'response'."
        }])

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            await agents_channel.publish({
                "type": "response",
                "agent": "WeatherAgent",
                "payload": "Unable to provide weather information due to a processing error."
            })
            return

        await agents_channel.publish({
            "type": "response",
            "agent": "WeatherAgent",
            "payload": reply.get("response", "Unable to provide weather information at this time.")
        })
    except Exception as e:
        console.print(f"[red]Error in WeatherAgent: {e}[/red]")

# MathAgent subscribes to math requests
@math_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "math_request")
async def handle_math_request(msg):
    try:
        query = msg["payload"]
        response = await math_agent.completion(messages=[{
            "role": "user",
            "content": f"Solve the following problem: {query}. Respond as JSON with key 'response'."
        }])

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            await agents_channel.publish({
                "type": "response",
                "agent": "MathAgent",
                "payload": "Unable to solve the math problem due to a processing error."
            })
            return

        await agents_channel.publish({
            "type": "response",
            "agent": "MathAgent",
            "payload": reply.get("response", "Unable to solve the math problem at this time.")
        })
    except Exception as e:
        console.print(f"[red]Error in MathAgent: {e}[/red]")

# Initialize ChatDisplayAgent
chat_display_agent = Agent(name="ChatDisplayAgent")

def clear_last_line():
    # sys.stdout.write("\x1b[1A")
    sys.stdout.write("\x1b[2K")

# ChatDisplayAgent subscribes to responses and prints them
@chat_display_agent.subscribe(channel=agents_channel,
                              filter_func=lambda msg: msg["type"] == "response")
async def display_response(msg):
    try:
        agent_name = msg.get("agent", "UnknownAgent")
        response = msg["payload"]
        style = AGENT_STYLES.get(agent_name, {"emoji": "❓", "color": "yellow"})
        emoji = style["emoji"]
        color = style["color"]
        # Display the response in a Rich Panel fitting all width

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
            if user_input.lower() == "exit":
                console.print("\n[bold red]Goodbye![/bold red]")
                stop_event.set()
                break
            else:
                await humans_channel.publish({
                    "type": "user_message",
                    "payload": user_input
                })
        except Exception as e:
            stop_event.set()

# Function to start all agents
async def start_agents():
    await asyncio.gather(
        triage_agent.run(),
        weather_agent.run(),
        math_agent.run(),
        chat_display_agent.run()
    )

# Function to stop all agents
async def stop_agents():
    await asyncio.gather(
        triage_agent.stop(),
        weather_agent.stop(),
        math_agent.stop(),
        chat_display_agent.stop()
    )
    await Channel.stop()

async def main():
    stop_event = asyncio.Event()
    try:
        console.print("[bold cyan]Welcome to the Multi-Agent Conversation Demo![/bold cyan]")
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
