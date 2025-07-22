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

logger = logging.getLogger("fetch_mcp_adapter")

if __name__ == "__main__":
    try:
        logger.info("Initializing Fetch MCP adapter")
        eggai_set_default_transport(lambda: KafkaTransport())
        logger.info("Starting Fetch adapter with uvx mcp-server-fetch")
        asyncio.run(eggai_mcp_adapter("Fetch", stdio_server_params=StdioServerParameters(
            command="uvx",
            args=["mcp-server-fetch"],
            env=None,
        )))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down Fetch adapter")
    except Exception as e:
        logger.error(f"Error in Fetch adapter: {str(e)}", exc_info=True)