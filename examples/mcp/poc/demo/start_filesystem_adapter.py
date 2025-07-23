#!/usr/bin/env python3
"""Standalone script to start the FileSystem MCP adapter."""

import sys
import os
import dotenv
import logging

# Load environment variables first
dotenv.load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from start_ticket_adapter import create_filesystem_adapter
from adapter_base import run_adapter

if __name__ == "__main__":
    print("📁 Starting FileSystem MCP adapter...")
    
    try:
        # Point to our test_files directory
        test_files_path = os.path.join(os.path.dirname(__file__), 'test_files')
        print(f"📂 Test files path: {test_files_path}")
        
        from mcp import StdioServerParameters
        from start_ticket_adapter import MCPAdapter
        
        # Create filesystem adapter pointing to our test directory
        print("🔧 Creating MCPAdapter...")
        adapter = MCPAdapter(
            "FileSystem",
            StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", test_files_path]
            )
        )
        print("✅ MCPAdapter created")
        
        print("🚀 Starting adapter...")
        run_adapter(adapter)
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()
        raise