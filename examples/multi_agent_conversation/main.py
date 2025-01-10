import asyncio

from eggai import Channel
from claims import claims_agent
from escalation import escalation_agent
from policy import policy_agent
from triage import triage_agent
from chat_display import chat_display_agent, console

async def start_agents():
    await asyncio.gather(
        triage_agent.run(),
        claims_agent.run(),
        policy_agent.run(),
        escalation_agent.run(),
        chat_display_agent.run()
    )

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
    from chat_display import ask_input, console
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

if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting...[/bold red]")
