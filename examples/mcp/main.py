#!/usr/bin/env python3
"""EggAI MCP Assistant - Streaming DSPy ReAct with MCP tools."""

import asyncio
from eggai import eggai_main
from agents.mcp_agent.agent import run_mcp_agent
from agents.chat_agent.agent import run_console_agent


@eggai_main
async def main():
    """Run MCP and console agents concurrently."""
    import aioconsole
    await aioconsole.aprint("🚀 Starting EggAI MCP Assistant...")
    
    await asyncio.gather(run_mcp_agent(), run_console_agent())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass