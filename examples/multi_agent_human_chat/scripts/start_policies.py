"""Convenience entry point to run the Policies Agent."""

import uvicorn


def main() -> None:
    """Launch the Policies Agent API using Uvicorn."""
    uvicorn.run("agents.policies.agent.main:api", host="0.0.0.0", port=8002)


if __name__ == "__main__":
    main()
