#!/usr/bin/env python3
"""
Development script for running the dataset generator directly.
For production use, install the package and use the `triage-generate` command.
"""
import sys
import os
import asyncio
import argparse
from dotenv import load_dotenv

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.triage_agent_dataset.__main__ import generate_dataset

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a triage agent dataset")
    parser.add_argument(
        "--output", "-o", 
        type=str, 
        default="dataset.jsonl", 
        help="Output file path (default: dataset.jsonl)"
    )
    parser.add_argument(
        "--temperatures", "-t", 
        type=float, 
        nargs="+", 
        default=[0.7, 0.8, 0.9],
        help="List of temperatures to use (default: 0.7 0.8 0.9)"
    )
    parser.add_argument(
        "--turns", "-u", 
        type=int, 
        nargs="+", 
        default=[1, 3, 5],
        help="List of turns to use (default: 1 3 5)"
    )
    parser.add_argument(
        "--total", "-n", 
        type=int, 
        help="Total number of examples to generate (overrides config value)"
    )
    
    args = parser.parse_args()
    
    print(f"Starting dataset generation to {args.output}...")
    # Run the dataset generation function
    asyncio.run(generate_dataset(
        output_file=args.output,
        temperatures=args.temperatures,
        turns=args.turns,
        total_target=args.total
    ))
