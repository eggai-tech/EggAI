import asyncio
import logging
from typing import List

from eggai import Agent, Channel
from eggai.schemas import Message
from mcp import Tool, InitializeResult, ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce noise from dependency packages
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("eggai_mcp_adapter")

async def eggai_mcp_adapter(
        agent_name: str,
        sse_url: str = None,
        stdio_server_params: StdioServerParameters = None
):
    logger.info(f"Starting MCP adapter for {agent_name}")
    
    def mcp_client():
        if stdio_server_params:
            logger.info(f"Using stdio client with command: {stdio_server_params.command} {' '.join(stdio_server_params.args)}")
            return stdio_client(stdio_server_params)
        if sse_url:
            logger.info(f"Using SSE client with URL: {sse_url}")
            return sse_client(sse_url)
        error_msg = "Either sse_url or server_params must be provided"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        logger.info("Establishing connection to MCP server")
        async with mcp_client() as streams:
            logger.info("Connection established, creating client session")
            async with ClientSession(streams[0], streams[1]) as session:
                tools: List[Tool]
                init_result: InitializeResult
                
                logger.info(f"Creating channels for {agent_name}")
                channel_in = Channel(f"eggai.mcp.{agent_name}.in")
                channel_out = Channel(f"eggai.mcp.{agent_name}.out")
                agent = Agent(agent_name)
                
                logger.info("Initializing MCP session")
                init_result = await session.initialize()
                logger.info(f"MCP session initialized with server: {init_result.serverInfo.name}")
                
                logger.info("Requesting available tools")
                list_res = await session.list_tools()
                tools = list_res.tools
                logger.info(f"Received {len(tools)} tools from MCP server")
                
                logger.info(f"{agent_name} bound with MCP server {init_result.serverInfo.name}")
                print(f"{agent_name} bound with mcp server {init_result.serverInfo.name}")
                
                # Define handler for tool calls
                @agent.subscribe(channel_in, filter_by_message=lambda msg: msg.get("type") == "call_tool")
                async def call_tool(msg: Message):
                    logger.info(f"Received tool call request: {msg.type}")
                    try:
                        # Extract correlation ID from message data
                        correlation_id = msg.data.get("correlation_id") 
                        if not correlation_id:
                            # Fall back to message ID if no correlation ID in data
                            correlation_id = msg.id
                            logger.warning(f"No correlation_id found in data, using message ID: {correlation_id}")
                            
                        tool_name = msg.data.get("tool")
                        tool_args = msg.data.get("arguments", None)
                        logger.info(f"Calling MCP tool: {tool_name} with args: {tool_args}")
                        
                        res = await session.call_tool(tool_name, arguments=tool_args)
                        logger.info(f"Tool call successful, result length: {len(str(res)) if res else 0}")
                        
                        # Create tool result message with CloudEvents format
                        response_msg = Message(
                            type="tool_result",
                            source=f"eggai.mcp.{agent_name}",
                            data={
                                "correlation_id": correlation_id,
                                "agent": agent_name,
                                "result": res
                            }
                        )
                        logger.debug(f"Publishing tool result message for correlation_id: {correlation_id}")
                        await channel_out.publish(response_msg)
                    except Exception as e:
                        logger.error(f"Error calling tool: {e}", exc_info=True)
                        print(f"Error calling tool: {e}")
                        
                        # Create error message with CloudEvents format
                        error_msg = Message(
                            type="tool_result",
                            source=f"eggai.mcp.{agent_name}",
                            data={
                                "correlation_id": correlation_id,
                                "agent": agent_name,
                                "result": {"content": f"Error calling tool: {str(e)}"}
                            }
                        )
                        logger.debug(f"Publishing error message for correlation_id: {correlation_id}")
                        await channel_out.publish(error_msg)

                # Define handler for tool listing
                @agent.subscribe(channel_in, filter_by_message=lambda msg: msg.get("type") == "list_tools")
                async def list_tools(msg: Message):
                    logger.info(f"Received tools list request: {msg.type}")
                    try:
                        # Extract correlation ID from message data
                        correlation_id = msg.data.get("correlation_id") 
                        if not correlation_id:
                            # Fall back to message ID if no correlation ID in data
                            correlation_id = msg.id
                            logger.warning(f"No correlation_id found in data, using message ID: {correlation_id}")
                        
                        # Create tools list message with CloudEvents format
                        response_msg = Message(
                            type="tools_list",
                            source=f"eggai.mcp.{agent_name}",
                            data={
                                "correlation_id": correlation_id,
                                "agent": agent_name,
                                "tools": tools
                            }
                        )
                        logger.info(f"Sending list of {len(tools)} tools to client")
                        logger.debug(f"Publishing tools list message for correlation_id: {correlation_id}")
                        await channel_out.publish(response_msg)
                    except Exception as e:
                        logger.error(f"Error listing tools: {e}", exc_info=True)
                        print(f"Error listing tools: {e}")
                        
                        # Create error message with CloudEvents format
                        error_msg = Message(
                            type="tools_list",
                            source=f"eggai.mcp.{agent_name}",
                            data={
                                "correlation_id": correlation_id,
                                "agent": agent_name,
                                "tools": []
                            }
                        )
                        logger.debug(f"Publishing error message for correlation_id: {correlation_id}")
                        await channel_out.publish(error_msg)

                # Start the agent and wait indefinitely
                logger.info(f"Starting {agent_name} agent")
                await agent.start()
                logger.info(f"{agent_name} agent started successfully, waiting for messages")
                
                # Create a future that never completes to keep the adapter running
                await asyncio.Future()
    except Exception as e:
        logger.error(f"Error in MCP adapter: {e}", exc_info=True)
        raise


