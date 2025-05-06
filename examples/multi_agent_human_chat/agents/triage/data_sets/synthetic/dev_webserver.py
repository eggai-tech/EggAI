#!/usr/bin/env python3
"""
Development script for running the webserver directly.
For production use, install the package and use the `triage-server` command.
"""
import sys
import os
import uvicorn
import argparse
from dotenv import load_dotenv

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start the Triage Dataset Manager web server")
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0", 
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=int(os.getenv("PORT", "8000")), 
        help="Port to bind the server to (default: 8000 or PORT env var)"
    )
    
    args = parser.parse_args()
    
    print(f"Starting development server on {args.host}:{args.port}...")
    uvicorn.run(
        "src.triage_webserver.app:app", 
        host=args.host, 
        port=args.port, 
        reload=True
    )
