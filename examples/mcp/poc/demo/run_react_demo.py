#!/usr/bin/env python3
"""
Run the DSPy ReAct agent demo with external tools.

This demonstrates:
1. Real DSPy ReAct agent with reasoning
2. External tool integration via adapters  
3. Kafka-based communication
4. Interactive console interface
"""

import asyncio
import logging
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from react_agent import ReactAgentWithExternalTools
from console_interface import ConsoleInterface
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# FileSystem adapter will be started separately

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce noise from dependencies
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def run_react_demo():
    """Run the complete ReAct demo."""
    
    print("🚀 Starting DSPy ReAct Agent Demo")
    print("=" * 50)
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable required")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-key-here'")
        return
        
    # FileSystem adapter should be started externally
    print("📁 FileSystem adapter should be running (start with make start-filesystem-adapter)")
    await asyncio.sleep(1)  # Brief pause
    
    # Start ReAct agent
    print("🧠 Starting DSPy ReAct agent...")
    react_agent = ReactAgentWithExternalTools()
    
    # Start console interface  
    print("💬 Starting console interface...")
    console = ConsoleInterface()
    
    try:
        # Start both systems
        await react_agent.start()
        await console.start()
        print("✅ All systems ready!\n")
        
        # Run interactive loop
        await console.run_interactive_loop()
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")
    except Exception as e:
        logger.error(f"Demo error: {e}")
        print(f"❌ Error: {e}")
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await react_agent.stop()
        await console.stop()
            
        print("👋 Demo complete")


def main():
    """Main entry point."""
    try:
        asyncio.run(run_react_demo())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()