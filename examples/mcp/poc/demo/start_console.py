#!/usr/bin/env python3
"""Standalone script to start the console interface."""

import asyncio
import sys
import os
import dotenv

# Load environment variables first
dotenv.load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from console_interface import ConsoleInterface

async def run():
    """Run the console interface."""
    print("💬 Starting console interface...")
    console = ConsoleInterface()
    await console.start()
    await console.run_interactive_loop()
    await console.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n👋 Console interface stopped.")