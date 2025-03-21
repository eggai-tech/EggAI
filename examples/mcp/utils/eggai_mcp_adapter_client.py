from eggai import Channel
from eggai.schemas import Message
import asyncio
import logging
import uuid

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce noise from dependency packages
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("eggai_mcp_adapter_client")

class EggaiMcpAdapterClient:
    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        logger.info(f"Creating MCP adapter client for {name}")
        self.channel_in = Channel(f"eggai.mcp.{name}.in")
        self.channel_out = Channel(f"eggai.mcp.{name}.out")
        self.pending_requests = {}

    async def _initialize(self):
        if not self._initialized:
            logger.info(f"Initializing {self.name} client and subscribing to output channel")
            await self.channel_out.subscribe(self._handle_mcp_output)
            self._initialized = True
            logger.info(f"{self.name} client initialized")

    async def _handle_mcp_output(self, msg: Message):
        message_type = msg.type
        correlation_id = msg.data.get("correlation_id") if msg.data else None
        logger.debug(f"Received message from {self.name}: type={message_type}, correlation_id={correlation_id}")

        if message_type == "tools_list":
            if correlation_id in self.pending_requests:
                # Extract tools from the data field
                tools = msg.data.get("tools", [])
                logger.info(f"Received tools list from {self.name}: {len(tools)} tools")
                future = self.pending_requests.pop(correlation_id)
                if future:
                    logger.debug(f"Resolving future for correlation_id: {correlation_id}")
                    future.set_result(tools)
            else:
                logger.warning(f"Received tools_list message with unknown correlation_id: {correlation_id}")
        elif message_type == "tool_result":
            if correlation_id in self.pending_requests:
                # Extract result from the data field
                result = msg.data.get("result")
                logger.info(f"Received tool result from {self.name}")
                logger.debug(f"Result: {str(result)[:100]}...")
                future = self.pending_requests.pop(correlation_id)
                if future:
                    logger.debug(f"Resolving future for correlation_id: {correlation_id}")
                    future.set_result(result)
            else:
                logger.warning(f"Received tool_result message with unknown correlation_id: {correlation_id}")
        else:
            logger.warning(f"Received unknown message type: {message_type}")

    async def list_tools(self):
        await self._initialize()
        correlation_id = uuid.uuid4().hex
        logger.info(f"Requesting tools list from {self.name}")
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[correlation_id] = future

        # Create tools list request message with CloudEvents format
        message = Message(
            type="list_tools",
            source=f"eggai.mcp.client.{self.name}",
            data={
                "correlation_id": correlation_id
            }
        )
        logger.debug(f"Publishing tools list request with correlation_id: {correlation_id}")
        await self.channel_in.publish(message)

        logger.debug(f"Waiting for tools list response from {self.name}")
        tools = await future
        logger.info(f"Received {len(tools)} tools from {self.name}")
        return tools

    async def call_tool(self, tool_name: str, arguments: dict):
        await self._initialize()
        correlation_id = uuid.uuid4().hex
        logger.info(f"Calling tool: {self.name}.{tool_name}")
        logger.debug(f"Tool arguments: {arguments}")
        
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[correlation_id] = future

        # Create tool call message with CloudEvents format
        message = Message(
            type="call_tool",
            source=f"eggai.mcp.client.{self.name}",
            data={
                "correlation_id": correlation_id,
                "tool": tool_name,
                "arguments": arguments
            }
        )
        logger.debug(f"Publishing tool call request with correlation_id: {correlation_id}")
        await self.channel_in.publish(message)

        logger.debug(f"Waiting for tool response from {self.name}.{tool_name}")
        result = await future
        logger.info(f"Received result from {self.name}.{tool_name}")
        return result