"""Console interface for the ReAct demo agent."""

import asyncio
import logging

import aioconsole
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport

logger = logging.getLogger(__name__)

eggai_set_default_transport(lambda: KafkaTransport())


class ConsoleInterface:
    """Interactive console interface for the ReAct agent."""
    
    def __init__(self):
        self.agent = Agent("ConsoleInterface")
        self.user_channel = Channel("user.input")
        self.response_channel = Channel("agent.response")
        self.waiting_for_response = asyncio.Event()
        self.waiting_for_response.set()  # Initially ready
        
    async def print_welcome(self):
        """Print welcome message."""
        await aioconsole.aprint("=" * 70)
        await aioconsole.aprint("🤖 DSPy ReAct Agent with FileSystem MCP Tools")
        await aioconsole.aprint("=" * 70)
        await aioconsole.aprint("This agent can access and manipulate files using MCP!")
        await aioconsole.aprint()
        await aioconsole.aprint("Try these filesystem commands:")
        await aioconsole.aprint("  • 'List the files in the directory'")
        await aioconsole.aprint("  • 'Read the project notes file'") 
        await aioconsole.aprint("  • 'What's in the meeting agenda?'")
        await aioconsole.aprint("  • 'Create a new file called summary.txt'")
        await aioconsole.aprint("  • 'Search for files containing \"external tools\"'")
        await aioconsole.aprint("  • 'Show me the config file contents'")
        await aioconsole.aprint()
        await aioconsole.aprint("Press Ctrl+C to exit")
        await aioconsole.aprint("=" * 70 + "\n")
        
    async def print_thinking(self):
        """Show thinking indicator."""
        await aioconsole.aprint("🤔 ReAct agent is thinking and using tools...", end="", flush=True)
        
    async def clear_thinking(self):
        """Clear thinking indicator."""
        await aioconsole.aprint("\r" + " " * 50 + "\r", end="", flush=True)
        
    async def start(self):
        """Start the console interface."""
        # Set up response handler
        @self.agent.subscribe(self.response_channel)
        async def handle_response(msg: Message):
            if msg.type == "agent_response":
                await self.clear_thinking()
                response = msg.data.get("response", "")
                await aioconsole.aprint(f"🤖 Agent: {response}\n")
                self.waiting_for_response.set()
        
        await self.agent.start()
        await self.print_welcome()
        
    async def run_interactive_loop(self):
        """Run the interactive console loop."""
        while True:
            try:
                # Wait for any previous response to complete
                await self.waiting_for_response.wait()
                
                # Get user input
                user_input = await aioconsole.ainput("You: ")
                
                if not user_input.strip():
                    continue
                    
                if user_input.lower() in ["exit", "quit", "bye"]:
                    await aioconsole.aprint("👋 Goodbye!")
                    break
                
                # Show thinking and send input
                self.waiting_for_response.clear()
                await self.print_thinking()
                
                msg = Message(
                    type="user_input",
                    source="console",
                    data={"input": user_input}
                )
                await self.user_channel.publish(msg)
                
            except (KeyboardInterrupt, EOFError):
                await self.clear_thinking()
                await aioconsole.aprint("\n👋 Goodbye!")
                break
            except Exception as e:
                await self.clear_thinking()
                await aioconsole.aprint(f"❌ Error: {e}")
                await aioconsole.aprint("Please try again.\n")
                self.waiting_for_response.set()
                
    async def stop(self):
        """Stop the console interface."""
        await self.agent.stop()