"""Start the Policies agent FastAPI server."""

import uvicorn

from agents.policies.config import settings
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent")


def main() -> None:
    """Run the Policies FastAPI application."""
    logger.info(f"Starting {settings.app_name} with FastAPI")
    uvicorn.run(
        "agents.policies.agent.main:api",
        host="0.0.0.0",
        port=8002,
        reload=False,
    )


if __name__ == "__main__":
    main()
