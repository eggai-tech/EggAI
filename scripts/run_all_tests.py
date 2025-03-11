#!/usr/bin/env python3
"""
Main entry point for running all tests.
"""
import sys
from scripts.run_tests import run_all

def main():
    """Run all tests."""
    try:
        return run_all()
    except Exception as e:
        print(f"Error during test run: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    exit(main())