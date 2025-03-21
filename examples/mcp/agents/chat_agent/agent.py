import asyncio
import json
import logging

import aioconsole
import dotenv
import litellm
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport
from utils.eggai_mcp_adapter_client import EggaiMcpAdapterClient
from aioconsole import aprint

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Reduce noise from dependency packages
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("chat_agent")

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
        },
    }


async def main():
    logger.info("Starting ChatAgent")
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
            ),
        }
    ]

    assistant_messages = asyncio.Queue()

    logger.info("Waiting for MCP adapters to initialize...")
    await asyncio.sleep(2)
    tool_registry = {}

    logger.info("Connecting to Fetch MCP adapter")
    fetch = EggaiMcpAdapterClient("Fetch")
    fetch_tools = await fetch.list_tools()
    logger.info(f"Retrieved {len(fetch_tools)} tools from Fetch adapter")
    tools = [mcp_tool_to_litellm_function(tool) for tool in fetch_tools]
    for tool in fetch_tools:
        tool_registry[tool["name"]] = fetch
        logger.debug(f"Registered fetch tool: {tool['name']}")

    logger.info("Connecting to FileSystem MCP adapter")
    file_system = EggaiMcpAdapterClient("FileSystem")
    fs_tools = await file_system.list_tools()
    logger.info(f"Retrieved {len(fs_tools)} tools from FileSystem adapter")
    tools.extend([mcp_tool_to_litellm_function(tool) for tool in fs_tools])
    for tool in fs_tools:
        tool_registry[tool["name"]] = file_system
        logger.debug(f"Registered filesystem tool: {tool['name']}")

    @agent.subscribe(channel, filter_by_message=lambda msg: msg.get("type") == "user")
    async def handle_message(msg: Message):
        # Extract content from data field
        content = msg.data.get("content")
        logger.info(f"Received user message: {content[:50]}...")
        messages.append({"role": "user", "content": content})

        async def process_message():
            logger.info(f"Sending completion request to model: {MODEL}")
            stream = await litellm.acompletion(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )

            first_assistant_token = True
            chunks = []
            tools_mode = False
            async for chunk in stream:
                if chunk.choices[0].delta.tool_calls:
                    tools_mode = True
                    logger.debug("Detected tool call in response")
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
                logger.info("Processing tool calls")
                for tool_call in built_message.choices[0].message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    adapter_name = tool_registry[function_name].name

                    logger.info(
                        f"Calling tool: {adapter_name}.{function_name} with args: {function_args}"
                    )
                    await aprint(f"Tool: {adapter_name}.{function_name}", end="")

                    function_response = await tool_registry[function_name].call_tool(
                        function_name, function_args
                    )
                    logger.info(
                        f"Tool response received: {str(function_response)[:100]}..."
                    )

                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response["content"],
                        }
                    )

                logger.info("Tool execution complete, generating follow-up response")
                return await process_message()

            logger.info("Completed message processing")
            return messages[-1]

        r = await process_message()
        await assistant_messages.put(r)

    logger.info("Starting agent")
    await agent.start()
    logger.info("Agent started successfully")

    while True:
        user_input = await aioconsole.ainput("You: ")
        if user_input == "exit":
            logger.info("Exit command received")
            break

        # Create user message with CloudEvents format
        user_message = Message(
            type="user", source="eggai.chat.user", data={"content": user_input}
        )
        logger.debug(f"Publishing user message: {user_input[:50]}...")
        await channel.publish(user_message)
        await assistant_messages.get()

    logger.info("Exiting Chat")
    print("Exiting Chat")


if __name__ == "__main__":
    try:
        logger.info("Starting MCP chat application")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        print("Exiting Chat")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")
