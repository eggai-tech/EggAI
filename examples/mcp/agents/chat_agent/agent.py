import asyncio

import aioconsole
import dotenv
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport

dotenv.load_dotenv()
eggai_set_default_transport(lambda: KafkaTransport())


async def print_welcome():
    """Print welcome message."""
    await aioconsole.aprint("=" * 60)
    await aioconsole.aprint("🤖 EggAI MCP Assistant")
    await aioconsole.aprint("=" * 60)
    await aioconsole.aprint("Connected to MCP servers with tools available")
    await aioconsole.aprint("Press Ctrl+C to exit")
    await aioconsole.aprint("=" * 60 + "\n")


async def print_thinking():
    """Show thinking indicator."""
    await aioconsole.aprint("🤔 Thinking...", end="", flush=True)


async def clear_thinking():
    """Clear thinking indicator."""
    await aioconsole.aprint("\r" + " "*20 + "\r", end="", flush=True)


async def run_console_agent():
    """Console agent with streaming support and tool notifications."""
    
    agent = Agent("ConsoleAgent")
    user_channel = Channel("user.input")
    assistant_channel = Channel("assistant.output")
    
    response_received = asyncio.Event()
    response_received.set()
    
    @agent.subscribe(assistant_channel)
    async def handle_assistant_message(msg: Message):
        if msg.type == "assistant_token":
            token = msg.data.get("token", "")
            is_first = msg.data.get("is_first", False)
            
            if is_first:
                await clear_thinking()
                await aioconsole.aprint(f"🤖 Assistant: {token}", end="", flush=True)
            else:
                await aioconsole.aprint(token, end="", flush=True)
                
        elif msg.type == "tool_notification":
            await clear_thinking()
            notification = msg.data.get("message", "")
            await aioconsole.aprint(f"{notification}")
            await print_thinking()
                
        elif msg.type == "assistant_end":
            await aioconsole.aprint("\n")
            response_received.set()
            
        elif msg.type == "assistant_response":
            # Legacy support
            await clear_thinking()
            response = msg.data.get("response", "")
            await aioconsole.aprint(f"🤖 Assistant: {response}\n")
            response_received.set()
    
    await agent.start()
    await asyncio.sleep(1.0)
    await print_welcome()
    
    while True:
        try:
            await response_received.wait()
            user_input = await aioconsole.ainput("You: ")
            
            if not user_input.strip():
                continue
            
            response_received.clear()
            await print_thinking()
            
            user_message = Message(
                type="user_input",
                source="console",
                data={"input": user_input}
            )
            await user_channel.publish(user_message)
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            await clear_thinking()
            await aioconsole.aprint("\n👋 Goodbye!")
            break
        except Exception as error:
            await clear_thinking()
            await aioconsole.aprint(f"❌ Error: {error}")
            await aioconsole.aprint("Please try again.\n")
            response_received.set()


if __name__ == "__main__":
    asyncio.run(run_console_agent())