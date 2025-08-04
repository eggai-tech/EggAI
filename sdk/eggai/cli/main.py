#!/usr/bin/env python3
"""
EggAI CLI Entry Point

Command-line interface for EggAI development tools.
"""

import sys

try:
    import click
except ImportError:
    print("Error: click is required for the CLI. Install with: pip install click")
    sys.exit(1)

from .wizard import create_app


@click.group()
@click.version_option()
def cli():
    """EggAI CLI - Tools for building agent applications."""
    pass


# Register commands
cli.add_command(create_app, name="create")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()