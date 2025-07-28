import aioconsole
import dotenv
from eggai import Channel, eggai_main
from eggai.schemas import Message
from eggai.transport import eggai_set_default_transport, KafkaTransport

dotenv.load_dotenv()
eggai_set_default_transport(lambda: KafkaTransport())

@eggai_main
async def console_loop():
    response_received = asyncio.Event()
    response_received.set()

    async def handle_assistant_response(message: Message):
        """Handle responses from the assistant."""
        if message.type == "agent_response":
            await aioconsole.aprint(f"\n🤖 \033[92mAssistant:\033[0m ", end="")
            await aioconsole.aprint(f"{message.data.get('assistant_response')}")
            response_received.set()

    await Channel("human.out").subscribe(handle_assistant_response)

    while True:
        try:
            await response_received.wait()
            # print emoji and cyan color for user input
            command = await aioconsole.ainput(
                "\n💬 \033[96mUser:\033[0m "
            )
            if command.lower() == "exit":
                break
        except (EOFError, KeyboardInterrupt):
            break

        await Channel("human.in").publish(Message(
            type="user_input",
            source="console",
            data={"user_message": command}
        ))

        response_received.clear()



if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(console_loop())
    except KeyboardInterrupt:
        print("\nExiting console...", flush=True)