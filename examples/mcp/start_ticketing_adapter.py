import asyncio

from eggai.transport import eggai_set_default_transport, KafkaTransport
import dotenv

from eggai_adapter.mcp import run_mcp_adapter
from schemas import TICKET_ADAPTER_NAME

dotenv.load_dotenv()

if __name__ == "__main__":
    eggai_set_default_transport(lambda: KafkaTransport())
    asyncio.run(
        run_mcp_adapter(TICKET_ADAPTER_NAME, "http://localhost:8000/sse")
    )