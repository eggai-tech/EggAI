#!/usr/bin/env python3
"""Standalone script to start the ReAct agent."""

import asyncio
import sys
import os
import dotenv

# Load environment variables first
dotenv.load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from react_agent import ReactAgentWithExternalTools

async def run():
    """Run the ReAct agent."""
    print("🧠 Starting DSPy ReAct agent...")
    
    # Set up logging to see what's happening
    import logging
    logging.basicConfig(level=logging.INFO)
    
    agent = ReactAgentWithExternalTools()
    print("📡 Agent created, starting setup...")
    await agent.start()
    print("✅ ReAct agent ready and listening...")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("🛑 ReAct agent stopping...")
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(run())