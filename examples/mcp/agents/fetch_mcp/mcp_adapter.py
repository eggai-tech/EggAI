import asyncio

from eggai.transport import eggai_set_default_transport, KafkaTransport
from mcp import StdioServerParameters

from utils.eggai_mcp_adapter import eggai_mcp_adapter

if __name__ == "__main__":
    try:
        eggai_set_default_transport(lambda: KafkaTransport())
        asyncio.run(eggai_mcp_adapter("Fetch", stdio_server_params=StdioServerParameters(
            command="uvx",
            args=["mcp-server-fetch"],
            env=None,
        )))
    except KeyboardInterrupt:
        print("Shutting down Fetch")