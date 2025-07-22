import asyncio
import logging

from eggai.transport import eggai_set_default_transport, KafkaTransport
from mcp import StdioServerParameters

from utils.eggai_mcp_adapter import eggai_mcp_adapter

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce noise from dependency packages
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("filesystem_mcp_adapter")

if __name__ == "__main__":
    try:
        logger.info("Initializing FileSystem MCP adapter")
        eggai_set_default_transport(lambda: KafkaTransport())
        logger.info("Starting FileSystem adapter with npx @modelcontextprotocol/server-filesystem")
        asyncio.run(eggai_mcp_adapter("FileSystem", stdio_server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "sandbox"],
            env=None,
        )))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down FileSystem adapter")
    except Exception as e:
        logger.error(f"Error in FileSystem adapter: {str(e)}", exc_info=True)