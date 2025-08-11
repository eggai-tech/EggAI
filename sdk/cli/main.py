#!/usr/bin/env python3
"""
EggAI CLI Entry Point

Command-line interface for EggAI development tools.
"""

import sys

try:
    import click
except ImportError:
    print("Error: CLI dependencies not installed. Install with: pip install eggai[cli]")
    sys.exit(1)

from .wizard import create_app

# Get version from package
try:
    from importlib.metadata import version

    __version__ = version("eggai")
except ImportError:
    # Python < 3.8
    from importlib_metadata import version

    __version__ = version("eggai")


@click.group()
@click.version_option(version=__version__)
def cli():
    """EggAI CLI - Tools for building agent applications."""
    pass


# Register commands
cli.add_command(create_app, name="init")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
