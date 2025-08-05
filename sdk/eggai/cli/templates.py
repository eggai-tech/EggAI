"""
Template generation for EggAI applications using Jinja2.

This module uses Jinja2 templates to generate boilerplate code for new EggAI applications.
"""

from pathlib import Path
from typing import TYPE_CHECKING

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    raise ImportError("jinja2 is required for template generation. Install with: pip install jinja2")

if TYPE_CHECKING:
    from .wizard import AppConfig


class TemplateGenerator:
    """Jinja2-based template generator for EggAI applications."""
    
    def __init__(self):
        # Get the templates directory path
        template_dir = Path(__file__).parent / "templates"
        
        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=False,
            lstrip_blocks=False
        )
    
    def generate_main_py(self, config: "AppConfig") -> str:
        """Generate the main.py file content."""
        template = self.env.get_template("main.py.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport,
            agents=config.agents
        )
    
    def generate_agent_file(self, agent_name: str) -> str:
        """Generate individual agent file content."""
        template = self.env.get_template("agent.py.j2")
        
        # Convert agent name to various formats
        agent_lower = agent_name.lower()
        agent_channel = agent_lower.replace("_", ".")
        
        return template.render(
            agent_name=agent_name,
            agent_function=agent_lower,
            agent_channel=agent_channel
        )
    
    def generate_agents_init(self) -> str:
        """Generate agents/__init__.py file."""
        template = self.env.get_template("agents_init.py.j2")
        return template.render()
    
    def generate_requirements_txt(self, config: "AppConfig") -> str:
        """Generate the requirements.txt file content."""
        template = self.env.get_template("requirements.txt.j2")
        return template.render(
            transport=config.transport,
            include_console=config.include_console
        )
    
    def generate_readme(self, config: "AppConfig") -> str:
        """Generate the README.md file content."""
        template = self.env.get_template("README.md.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport,
            agents=config.agents
        )
    
    def generate_env_file(self) -> str:
        """Generate .env file for Kafka configuration."""
        template = self.env.get_template("env.j2")
        return template.render()
    
    def generate_console_file(self, config: "AppConfig") -> str:
        """Generate console.py file for interactive frontend."""
        template = self.env.get_template("console.py.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport
        )


# Create a global instance
_generator = TemplateGenerator()

# Export the generator functions for backward compatibility
def generate_main_py(config: "AppConfig") -> str:
    """Generate the main.py file content."""
    return _generator.generate_main_py(config)

def generate_agent_file(agent_name: str) -> str:
    """Generate individual agent file content."""
    return _generator.generate_agent_file(agent_name)

def generate_agents_init() -> str:
    """Generate agents/__init__.py file."""
    return _generator.generate_agents_init()

def generate_requirements_txt(config: "AppConfig") -> str:
    """Generate the requirements.txt file content."""
    return _generator.generate_requirements_txt(config)

def generate_readme(config: "AppConfig") -> str:
    """Generate the README.md file content."""
    return _generator.generate_readme(config)

def generate_env_file() -> str:
    """Generate .env file for Kafka configuration."""
    return _generator.generate_env_file()

def generate_console_file(config: "AppConfig") -> str:
    """Generate console.py file for interactive frontend."""
    return _generator.generate_console_file(config)