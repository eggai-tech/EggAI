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
                # Check for error in response
                error = msg.data.get("error")
                if error:
                    logger.error(f"Error in tools list response: {error.get('message')}")
                    future = self.pending_requests.pop(correlation_id)
                    if future:
                        logger.debug(f"Rejecting future with error for correlation_id: {correlation_id}")
                        future.set_exception(Exception(f"MCP Error: {error.get('message')}"))
                    return
                
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
                # Check for error in response
                error = msg.data.get("error")
                if error:
                    error_message = error.get('message', 'Unknown error')
                    error_type = error.get('type', 'Error')
                    logger.error(f"Error in tool result: {error_type}: {error_message}")
                    
                    future = self.pending_requests.pop(correlation_id)
                    if future:
                        # Return result with error indication rather than raising exception
                        # This allows the client to still get the error content
                        logger.debug(f"Resolving future with error for correlation_id: {correlation_id}")
                        result = msg.data.get("result", {"content": f"Error: {error_message}"})
                        future.set_result(result)
                    return
                
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

    async def list_tools(self, timeout=10.0):
        """
        Request list of available tools from the MCP adapter
        
        Args:
            timeout: Maximum time to wait for a response in seconds
            
        Returns:
            List of tools
            
        Raises:
            TimeoutError: If the request times out
            Exception: If an error occurs during the request
        """
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

        try:
            logger.debug(f"Waiting for tools list response from {self.name} (timeout: {timeout}s)")
            tools = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Received {len(tools)} tools from {self.name}")
            return tools
        except asyncio.TimeoutError:
            # Clean up the pending request
            if correlation_id in self.pending_requests:
                self.pending_requests.pop(correlation_id)
            logger.error(f"Timeout waiting for tools list response from {self.name}")
            raise TimeoutError(f"Timeout waiting for tools list response from {self.name} after {timeout} seconds")

    async def call_tool(self, tool_name: str, arguments: dict, timeout=30.0):
        """
        Call a tool on the MCP adapter
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            timeout: Maximum time to wait for a response in seconds
            
        Returns:
            Tool result
            
        Raises:
            TimeoutError: If the request times out
            Exception: If an error occurs during the tool call
        """
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

        try:
            logger.debug(f"Waiting for tool response from {self.name}.{tool_name} (timeout: {timeout}s)")
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Received result from {self.name}.{tool_name}")
            return result
        except asyncio.TimeoutError:
            # Clean up the pending request
            if correlation_id in self.pending_requests:
                self.pending_requests.pop(correlation_id)
            logger.error(f"Timeout waiting for tool response from {self.name}.{tool_name}")
            return {
                "content": f"Error: Tool call to {self.name}.{tool_name} timed out after {timeout} seconds",
                "error": {
                    "type": "TimeoutError",
                    "message": f"Tool call timed out after {timeout} seconds",
                    "tool": tool_name,
                    "arguments": arguments
                }
            }