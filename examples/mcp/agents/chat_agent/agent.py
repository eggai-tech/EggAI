import asyncio
import json

import aioconsole
import dotenv
import litellm
from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport
from utils.eggai_mcp_adapter_client import EggaiMcpAdapterClient
from aioconsole import aprint

dotenv.load_dotenv()

eggai_set_default_transport(lambda: KafkaTransport())

MODEL = "openai/gpt-4-turbo"


def mcp_tool_to_litellm_function(mcp_tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool["description"],
            "parameters": mcp_tool["inputSchema"],
        }
    }


async def main():
    agent = Agent("ChatAgent")
    channel = Channel("eggai.chat")
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant running in a CLI environment. "
                "You must always respond in plain text. "
                "Do not use any Markdown formatting, including asterisks, underscores, "
                "backticks, or other special characters. "
                "Do not use bold, italics, headings, lists, or code blocks. "
                "Provide only plain text responses with standard punctuation and spacing. "
                "When choosing to do file operation, you should use list_allowed_directories first."
            )
        }
    ]

    assistant_messages = asyncio.Queue()
    
    await asyncio.sleep(2)
    tool_registry = {}

    fetch = EggaiMcpAdapterClient("Fetch")
    fetch_tools = await fetch.list_tools()
    tools = [mcp_tool_to_litellm_function(tool) for tool in fetch_tools]
    for tool in fetch_tools:
        tool_registry[tool["name"]] = fetch

    file_system = EggaiMcpAdapterClient("FileSystem")
    fs_tools = await file_system.list_tools()
    tools.extend([mcp_tool_to_litellm_function(tool) for tool in fs_tools])
    for tool in fs_tools:
        tool_registry[tool["name"]] = file_system

    @agent.subscribe(channel, filter_by_message=lambda msg: msg.get("type") == "user")
    async def handle_message(msg):
        content = msg.get("content")
        messages.append({"role": "user", "content": content})

        async def process_message():
            stream = await litellm.acompletion(model=MODEL, messages=messages, tools=tools, tool_choice="auto", stream=True)

            first_assistant_token = True
            chunks = []
            tools_mode = False
            async for chunk in stream:
                if chunk.choices[0].delta.tool_calls:
                    tools_mode = True
                if not tools_mode:
                    if first_assistant_token:
                        first_assistant_token = False
                        await aprint("Assistant: ", end="")
                    await aprint(chunk.choices[0].delta.content or "", end="")
                if chunk.choices[0].finish_reason:
                    await aprint("\n", end="")
                    break
                chunks.append(chunk)

            built_message = litellm.stream_chunk_builder(chunks, messages=messages)
            messages.append(built_message.choices[0].message)
            if tools_mode:
                for tool_call in built_message.choices[0].message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    await aprint("Tool:", tool_registry[function_name].name + "." + function_name, end="")
                    function_response = await tool_registry[function_name].call_tool(function_name, function_args)
                    messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name,
                                     "content": function_response["content"]})

                return await process_message()

            return messages[-1]

        r = await process_message()
        await assistant_messages.put(r)

    await agent.start()

    while True:
        message = await aioconsole.ainput("You: ")
        if message == "exit":
            break
        await channel.publish({"type": "user", "content": message})
        await assistant_messages.get()

    print("Exiting Chat")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting Chat")