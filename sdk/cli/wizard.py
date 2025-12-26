"""
EggAI Application Wizard

Interactive CLI wizard for creating new EggAI applications with custom configurations.
"""

import sys
from importlib.metadata import version
from pathlib import Path

import click

from .templates import (
    generate_agent_file,
    generate_agents_init,
    generate_common_models_file,
    generate_console_file,
    generate_env_file,
    generate_main_py,
    generate_readme,
    generate_requirements_txt,
)

EGGAI_VERSION = version("eggai")


def agent_name_to_filename(agent_name: str) -> str:
    """Convert CamelCase agent name to snake_case filename without Agent suffix."""
    # Remove Agent suffix for filename
    name = agent_name
    if name.endswith("Agent"):
        name = name[:-5]  # Remove "Agent"

    # Convert CamelCase to snake_case
    import re

    # Add underscore before uppercase letters (except the first one)
    snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return snake_case.lower()


class Agent:
    """Represents an agent configuration."""

    def __init__(self, name: str):
        self.name = name
        self.filename = agent_name_to_filename(name)
        self.function_name = self.filename  # snake_case function name


class AppConfig:
    """Represents the complete application configuration."""

    def __init__(self):
        self.transport: str = ""
        self.agents: list[Agent] = []
        self.project_name: str = ""
        self.target_dir: Path = Path(".")
        self.include_console: bool = False


def show_logo():
    """Display the EggAI logo and version."""
    logo = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║    ███████╗ ██████╗  ██████╗        █████╗ ██╗                ║
    ║    ██╔════╝██╔════╝ ██╔════╝       ██╔══██╗██║                ║
    ║    █████╗  ██║  ███╗██║  ███╗█████╗███████║██║                ║
    ║    ██╔══╝  ██║   ██║██║   ██║╚════╝██╔══██║██║                ║
    ║    ███████╗╚██████╔╝╚██████╔╝      ██║  ██║██║                ║
    ║    ╚══════╝ ╚═════╝  ╚═════╝       ╚═╝  ╚═╝╚═╝                ║
    ║                                                               ║
    ║               Multi-Agent Meta Framework                      ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """

    click.echo(click.style(logo, fg="cyan", bold=True))
    click.echo(
        click.style(
            f"                            Version {EGGAI_VERSION}",
            fg="green",
            bold=True,
        )
    )
    click.echo(
        click.style("                  https://eggai-tech.github.io/EggAI/", fg="blue")
    )
    click.echo()


def show_wizard_header():
    """Display the wizard header after logo."""
    click.echo("=" * 67)
    click.echo(click.style("🚀 EggAI Application Wizard", fg="yellow", bold=True))
    click.echo("=" * 67)


def prompt_transport() -> str:
    """Prompt user to select transport type."""
    click.echo("\nStep 1: Select Transport Layer")
    click.echo("The transport layer handles message passing between agents.")

    transport_options = {
        "1": ("kafka", "Kafka Transport (for distributed apps)"),
        "2": ("inmemory", "In-Memory Transport (for single-process apps)"),
    }

    click.echo("\nAvailable transport options:")
    for key, (_, description) in transport_options.items():
        click.echo(f"  {key}. {description}")

    while True:
        choice = click.prompt("\nSelect transport", type=str, default="1")
        if choice in transport_options:
            transport_type, description = transport_options[choice]
            click.echo(f"✓ Selected: {description}")
            return transport_type
        else:
            click.echo("❌ Invalid choice. Please select 1 or 2.")


def normalize_agent_name(name: str) -> str:
    """Normalize agent name to proper CamelCase format with Agent suffix."""
    if not name.strip():
        return "Agent"

    # Split on underscores and spaces, clean each part
    parts = []
    for part in name.replace("_", " ").split():
        clean_part = "".join(c for c in part if c.isalnum())
        if clean_part:
            # Capitalize first letter, lowercase the rest
            parts.append(clean_part[0].upper() + clean_part[1:].lower())

    if not parts:
        return "Agent"

    # Join parts for CamelCase
    clean_name = "".join(parts)

    # Add Agent suffix if not present
    if not clean_name.endswith("Agent"):
        clean_name += "Agent"

    return clean_name


def parse_agents_string(agents_string: str) -> list[Agent]:
    """Parse comma-separated agent names from CLI parameter."""
    if not agents_string:
        return []

    agents = []
    for name in agents_string.split(","):
        normalized_name = normalize_agent_name(name.strip())
        agents.append(Agent(normalized_name))

    return agents


def prompt_agents() -> list[Agent]:
    """Prompt user to configure agents using a loop."""
    click.echo("\n" + "-" * 50)
    click.echo("Step 2: Configure Agents")
    click.echo(
        "Agents are the core components that process messages and perform tasks."
    )

    agents = []
    agent_count = 1

    while True:
        click.echo(f"\n--- Agent {agent_count} Configuration ---")

        while True:
            name = click.prompt(f"Enter name for agent {agent_count}", type=str)
            if name.strip():
                normalized_name = normalize_agent_name(name)
                agent = Agent(normalized_name)
                agents.append(agent)
                click.echo(f"✓ Agent '{normalized_name}' configured")
                break
            else:
                click.echo("❌ Agent name cannot be empty.")

        agent_count += 1

        if not click.confirm("\nAdd another agent?", default=False):
            break

    return agents


def prompt_console_option() -> bool:
    """Prompt user if they want to include a console frontend using selectable list."""
    click.echo("\n" + "-" * 50)
    click.echo("Step 3: Console Frontend")
    click.echo("Select optional features to include in your application.")

    # Available options
    options = [
        {
            "name": "Add Console Interface",
            "description": "Interactive chat interface in the terminal",
            "value": True,
            "selected": False,
        }
    ]

    # Check if we can use interactive mode
    try:
        import termios
        import tty

        has_termios = True and sys.stdin.isatty()
    except ImportError:
        has_termios = False

    if not has_termios:
        # Fallback to simple prompt for non-interactive environments
        click.echo("\nAvailable options:")
        click.echo(
            "  • Add Console Interface - Interactive chat interface in the terminal"
        )
        return click.confirm(
            "\nInclude console frontend for interactive chat?", default=True
        )

    current_option = 0

    def display_options():
        click.echo(
            "\nAvailable options (use ↑↓ arrows to navigate, SPACE to toggle, ENTER to confirm):"
        )
        for i, option in enumerate(options):
            marker = "→" if i == current_option else " "
            checkbox = "☑" if option["selected"] else "☐"
            click.echo(f"  {marker} {checkbox} {option['name']}")
            if i == current_option:
                click.echo(f"      └─ {option['description']}")

    def get_char():
        """Get a single character from stdin without pressing enter."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            char = sys.stdin.read(1)
            # Handle arrow keys (escape sequences)
            if char == "\x1b":  # ESC
                char += sys.stdin.read(2)
            return char
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Main selection loop
    while True:
        click.clear()
        click.echo("\n" + "-" * 50)
        click.echo("Step 3: Console Frontend")
        click.echo("Select optional features to include in your application.")

        display_options()

        click.echo(
            f"\nSelected features: {sum(1 for opt in options if opt['selected'])}"
        )
        click.echo("Press ENTER to continue...")

        try:
            char = get_char()

            if char == "\r" or char == "\n":  # Enter key
                break
            elif char == "\x1b[A":  # Up arrow
                current_option = (current_option - 1) % len(options)
            elif char == "\x1b[B":  # Down arrow
                current_option = (current_option + 1) % len(options)
            elif char == " ":  # Space key
                options[current_option]["selected"] = not options[current_option][
                    "selected"
                ]
            elif char == "q" or char == "\x03":  # Q or Ctrl+C
                click.echo("\n❌ Aborted.")
                sys.exit(1)
        except KeyboardInterrupt:
            click.echo("\n❌ Aborted.")
            sys.exit(1)

    # Return True if console interface was selected
    return options[0]["selected"]


def prompt_project_details() -> tuple[str, Path]:
    """Prompt for project name and target directory."""
    click.echo("\n" + "-" * 50)
    click.echo("Step 4: Project Configuration")

    project_name = click.prompt("Enter project name", type=str, default="my_eggai_app")
    # Sanitize project name for Python module naming (replace hyphens with underscores)
    project_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in project_name.strip()
    )
    project_name = project_name.replace("-", "_")

    target_dir = click.prompt("Enter target directory", type=str, default=".")
    target_path = Path(target_dir).resolve()

    if target_path.exists() and any(target_path.iterdir()):
        if not click.confirm(f"Directory '{target_path}' is not empty. Continue?"):
            click.echo("❌ Aborted.")
            sys.exit(1)

    return project_name, target_path


def create_project_structure(config: AppConfig) -> None:
    """Create the project directory structure and files."""
    click.echo("\n" + "-" * 50)
    click.echo("Step 5: Initializing Project")

    # Create root project directory inside target directory
    root_project_dir = config.target_dir / config.project_name
    root_project_dir.mkdir(parents=True, exist_ok=True)

    # Create Python package directory inside root project directory
    python_package_dir = root_project_dir / config.project_name
    python_package_dir.mkdir(parents=True, exist_ok=True)

    # Generate package __init__.py
    package_init_file = python_package_dir / "__init__.py"
    package_init_file.write_text("# Generated EggAI project package\n")
    click.echo(f"✓ Created {package_init_file}")

    # Create agents directory inside Python package
    agents_dir = python_package_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # Generate agents/__init__.py
    agents_init_content = generate_agents_init()
    agents_init_file = agents_dir / "__init__.py"
    agents_init_file.write_text(agents_init_content)
    click.echo(f"✓ Created {agents_init_file}")

    # Generate individual agent files
    for agent in config.agents:
        agent_content = generate_agent_file(
            agent.name, config.project_name, config.include_console
        )
        agent_file = agents_dir / f"{agent.filename}.py"
        agent_file.write_text(agent_content)
        click.echo(f"✓ Created {agent_file}")

    # Generate main.py inside Python package
    main_content = generate_main_py(config)
    main_file = python_package_dir / "main.py"
    main_file.write_text(main_content)
    click.echo(f"✓ Created {main_file}")

    # Generate models.py inside Python package
    models_content = generate_common_models_file(config)
    models_file = python_package_dir / "models.py"
    models_file.write_text(models_content)
    click.echo(f"✓ Created {models_file}")

    # Create console.py inside Python package if enabled
    if config.include_console:
        console_content = generate_console_file(config)
        console_file = python_package_dir / "console.py"
        console_file.write_text(console_content)
        click.echo(f"✓ Created {console_file}")

    # Generate requirements.txt in root project directory
    requirements_content = generate_requirements_txt(config)
    req_file = root_project_dir / "requirements.txt"
    req_file.write_text(requirements_content)
    click.echo(f"✓ Created {req_file}")

    # Generate README.md in root project directory
    readme_content = generate_readme(config)
    readme_file = root_project_dir / "README.md"
    readme_file.write_text(readme_content)
    click.echo(f"✓ Created {readme_file}")

    # Create .env file in root project directory if using Kafka
    if config.transport == "kafka":
        env_content = generate_env_file()
        env_file = root_project_dir / ".env"
        env_file.write_text(env_content)
        click.echo(f"✓ Created {env_file}")

    # Update config.target_dir to point to the root project directory for final message
    config.target_dir = root_project_dir


@click.command()
@click.option("--target-dir", type=str, help="Target directory for the new project")
@click.option("--project-name", type=str, help="Name of the new project")
@click.option(
    "--transport",
    type=click.Choice(["kafka", "inmemory"]),
    help="Transport layer (kafka or inmemory)",
)
@click.option(
    "--agents", type=str, help="Comma-separated agent names (e.g., Order,Email)"
)
@click.option(
    "--enable-console/--no-console", default=None, help="Include console frontend"
)
def create_app(
    target_dir: str = None,
    project_name: str = None,
    transport: str = None,
    agents: str = None,
    enable_console: bool = None,
):
    """Initialize a new EggAI application using an interactive wizard."""

    # Show logo and wizard header first
    show_logo()
    show_wizard_header()

    config = AppConfig()

    # Step 1: Transport selection
    if transport:
        config.transport = transport
        click.echo(f"✓ Using transport: {transport}")
    else:
        config.transport = prompt_transport()

    # Step 2: Agent configuration
    if agents:
        config.agents = parse_agents_string(agents)
        if not config.agents:
            click.echo("❌ No valid agents found in --agents parameter")
            sys.exit(1)
        click.echo(
            f"✓ Configured agents: {', '.join(agent.name for agent in config.agents)}"
        )
    else:
        config.agents = prompt_agents()

    # Step 3: Console frontend option
    if enable_console is not None:
        config.include_console = enable_console
        click.echo(f"✓ Console frontend: {'Yes' if enable_console else 'No'}")
    else:
        config.include_console = prompt_console_option()

    # Step 4: Project details
    if project_name and target_dir:
        # Sanitize project name for Python module naming
        config.project_name = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in project_name.strip()
        )
        config.project_name = config.project_name.replace("-", "_")
        config.target_dir = Path(target_dir).resolve()
        click.echo(f"✓ Project: {config.project_name} at {config.target_dir}")
    else:
        config.project_name, config.target_dir = prompt_project_details()

    # Step 5: Generate project
    create_project_structure(config)

    # Success message
    click.echo("\n" + "=" * 50)
    click.echo("🎉 Project initialized successfully!")
    click.echo("=" * 50)
    click.echo(f"Project: {config.project_name}")
    click.echo(f"Location: {config.target_dir}")
    click.echo(f"Transport: {config.transport}")
    click.echo(f"Agents: {', '.join(agent.name for agent in config.agents)}")
    click.echo(f"Console: {'Yes' if config.include_console else 'No'}")

    click.echo("\nNext steps:")
    click.echo(f"1. cd {config.target_dir}")
    click.echo("2. pip install -r requirements.txt")
    if config.transport == "kafka":
        click.echo("3. Set up Kafka server (see README.md)")
        click.echo("4. Configure .env file with your Kafka settings")
        click.echo(f"5. python -m {config.project_name}.main")
        if config.include_console:
            click.echo(
                f"6. python -m {config.project_name}.console  # For interactive chat"
            )
    else:
        click.echo(f"3. python -m {config.project_name}.main")
        if config.include_console:
            click.echo(
                f"4. python -m {config.project_name}.console  # For interactive chat"
            )


if __name__ == "__main__":
    create_app()
