"""
EggAI Application Wizard

Interactive CLI wizard for creating new EggAI applications with custom configurations.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    import click
except ImportError:
    print("Error: click is required for the CLI. Install with: pip install click")
    sys.exit(1)

from .templates import (
    generate_main_py, 
    generate_requirements_txt, 
    generate_readme,
    generate_agent_file,
    generate_agents_init,
    generate_env_file
)


class Agent:
    """Represents an agent configuration."""
    
    def __init__(self, name: str):
        self.name = name


class AppConfig:
    """Represents the complete application configuration."""
    
    def __init__(self):
        self.transport: str = ""
        self.agents: List[Agent] = []
        self.project_name: str = ""
        self.target_dir: Path = Path(".")


def prompt_transport() -> str:
    """Prompt user to select transport type."""
    click.echo("\n" + "="*50)
    click.echo("🚀 EggAI Application Wizard")
    click.echo("="*50)
    
    click.echo("\nStep 1: Select Transport Layer")
    click.echo("The transport layer handles message passing between agents.")
    
    transport_options = {
        "1": ("inmemory", "In-Memory Transport (for single-process apps)"),
        "2": ("kafka", "Kafka Transport (for distributed apps)")
    }
    
    click.echo("\nAvailable transport options:")
    for key, (value, description) in transport_options.items():
        click.echo(f"  {key}. {description}")
    
    while True:
        choice = click.prompt("\nSelect transport", type=str, default="1")
        if choice in transport_options:
            transport_type, description = transport_options[choice]
            click.echo(f"✓ Selected: {description}")
            return transport_type
        else:
            click.echo("❌ Invalid choice. Please select 1 or 2.")


def prompt_agents() -> List[Agent]:
    """Prompt user to configure agents."""
    click.echo("\n" + "-"*50)
    click.echo("Step 2: Configure Agents")
    click.echo("Agents are the core components that process messages and perform tasks.")
    
    while True:
        try:
            num_agents = click.prompt("\nHow many agents do you want to create?", type=int, default=1)
            if num_agents > 0:
                break
            else:
                click.echo("❌ Number of agents must be greater than 0.")
        except (ValueError, click.Abort):
            click.echo("❌ Please enter a valid number.")
    
    agents = []
    for i in range(num_agents):
        click.echo(f"\n--- Agent {i+1} Configuration ---")
        
        while True:
            name = click.prompt(f"Enter name for agent {i+1}", type=str)
            if name.strip():
                # Convert to valid Python identifier
                name = "".join(c if c.isalnum() or c == "_" else "_" for c in name.strip())
                if name[0].isdigit():
                    name = f"agent_{name}"
                break
            else:
                click.echo("❌ Agent name cannot be empty.")
        
        agent = Agent(name)
        agents.append(agent)
        click.echo(f"✓ Agent '{name}' configured")
    
    return agents


def prompt_project_details() -> tuple[str, Path]:
    """Prompt for project name and target directory."""
    click.echo("\n" + "-"*50)
    click.echo("Step 3: Project Configuration")
    
    project_name = click.prompt("Enter project name", type=str, default="my_eggai_app")
    project_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name.strip())
    
    target_dir = click.prompt("Enter target directory", type=str, default=".")
    target_path = Path(target_dir).resolve()
    
    if target_path.exists() and any(target_path.iterdir()):
        if not click.confirm(f"Directory '{target_path}' is not empty. Continue?"):
            click.echo("❌ Aborted.")
            sys.exit(1)
    
    return project_name, target_path


def create_project_structure(config: AppConfig) -> None:
    """Create the project directory structure and files."""
    click.echo("\n" + "-"*50)
    click.echo("Step 4: Generating Project")
    
    # Create target directory if it doesn't exist
    config.target_dir.mkdir(parents=True, exist_ok=True)
    
    # Create agents directory
    agents_dir = config.target_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    
    # Generate agents/__init__.py
    agents_init_content = generate_agents_init()
    agents_init_file = agents_dir / "__init__.py"
    agents_init_file.write_text(agents_init_content)
    click.echo(f"✓ Created {agents_init_file}")
    
    # Generate individual agent files
    for agent in config.agents:
        agent_content = generate_agent_file(agent.name)
        agent_file = agents_dir / f"{agent.name.lower()}.py"
        agent_file.write_text(agent_content)
        click.echo(f"✓ Created {agent_file}")
    
    # Generate main.py
    main_content = generate_main_py(config)
    main_file = config.target_dir / "main.py"
    main_file.write_text(main_content)
    click.echo(f"✓ Created {main_file}")
    
    # Generate requirements.txt
    requirements_content = generate_requirements_txt(config)
    req_file = config.target_dir / "requirements.txt"
    req_file.write_text(requirements_content)
    click.echo(f"✓ Created {req_file}")
    
    # Generate README.md
    readme_content = generate_readme(config)
    readme_file = config.target_dir / "README.md"
    readme_file.write_text(readme_content)
    click.echo(f"✓ Created {readme_file}")
    
    # Create .env file if using Kafka
    if config.transport == "kafka":
        env_content = generate_env_file()
        env_file = config.target_dir / ".env"
        env_file.write_text(env_content)
        click.echo(f"✓ Created {env_file}")


@click.command()
@click.option("--target-dir", type=str, help="Target directory for the new project")
@click.option("--project-name", type=str, help="Name of the new project")
def create_app(target_dir: str = None, project_name: str = None):
    """Create a new EggAI application using an interactive wizard."""
    
    config = AppConfig()
    
    # Step 1: Transport selection
    config.transport = prompt_transport()
    
    # Step 2: Agent configuration
    config.agents = prompt_agents()
    
    # Step 3: Project details
    if project_name and target_dir:
        config.project_name = project_name
        config.target_dir = Path(target_dir).resolve()
    else:
        config.project_name, config.target_dir = prompt_project_details()
    
    # Step 4: Generate project
    create_project_structure(config)
    
    # Success message
    click.echo("\n" + "="*50)
    click.echo("🎉 Project created successfully!")
    click.echo("="*50)
    click.echo(f"Project: {config.project_name}")
    click.echo(f"Location: {config.target_dir}")
    click.echo(f"Transport: {config.transport}")
    click.echo(f"Agents: {', '.join(agent.name for agent in config.agents)}")
    
    click.echo("\nNext steps:")
    click.echo(f"1. cd {config.target_dir}")
    click.echo("2. pip install -r requirements.txt")
    if config.transport == "kafka":
        click.echo("3. Set up Kafka server (see README.md)")
        click.echo("4. Configure .env file with your Kafka settings")
        click.echo("5. python main.py")
    else:
        click.echo("3. python main.py")


if __name__ == "__main__":
    create_app()