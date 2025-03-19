import asyncio

from eggai.transport import eggai_set_default_transport, KafkaTransport
from mcp import StdioServerParameters

from mcp_utils import mcp_sse_to_eggai

if __name__ == "__main__":
    try:
        eggai_set_default_transport(lambda: KafkaTransport())
        asyncio.run(mcp_sse_to_eggai("FileSystemAgent", stdio_server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "sandbox"],
            env=None,
        )))
    except KeyboardInterrupt:
        print("Shutting down FileSystemAgent")
